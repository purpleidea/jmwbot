#!/usr/bin/python
# -*- coding: utf-8 -*-
"""JMWbot
Bug johnmark about his todo list.

Based on the Twisted Matrix Laboratories example bot.
"""
# Copyright (C) 2012-2014+ James Shubin
# Written by James Shubin <james@shubin.ca>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.python import log

# system imports
import os, sys, time, pickle

class Store:
	def __init__(self, filename='data.dat'):
		self.filename = filename
		self.lastseenat = 0
		self.reminders = []
		self.maxid = 0
		if not os.path.exists(self.filename):
			self.save()	# initialize empty file

	def load(self):
		with open(self.filename, 'rb') as input:
			self.lastseenat = pickle.load(input)
			self.reminders = pickle.load(input)
			self.maxid = pickle.load(input)

	def save(self):
		with open(self.filename, 'wb') as output:
			pickle.dump(self.lastseenat, output, pickle.HIGHEST_PROTOCOL)
			pickle.dump(self.reminders, output, pickle.HIGHEST_PROTOCOL)
			pickle.dump(self.maxid, output, pickle.HIGHEST_PROTOCOL)

	def read(self, key):
		self.load()
		return getattr(self, key)

	def write(self, key, value):
		setattr(self, key, value)
		self.save()

class MessageLogger:
	"""
	An independent logger class (because separation of application
	and protocol logic is a good thing).
	"""
	def __init__(self, file):
		self.file = file

	def log(self, message):
		"""Write a message to the file."""
		timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
		self.file.write('%s %s\n' % (timestamp, message))
		self.file.flush()

	def close(self):
		self.file.close()


class JMWBot(irc.IRCClient):
	"""A JMW IRC bot."""

	def __init__(self, store):
		#irc.IRCClient.__init__(self)
		self.store = store
		self.nickname = 'JMWbot'
		self.jmw = 'johnmark'		# jmw's nickname on irc
		self.remind = '@remind'		# action text
		self.done = '@done'		# action text
		self.list = '@list'		# action text
		self.about = '@about'		# action text
		self.delta = 60*60*24		# maximum once per day
		self.lastseenat = self.store.read('lastseenat')
		self.reminders = self.store.read('reminders')
		self.maxid = self.store.read('maxid')

	def connectionMade(self):
		irc.IRCClient.connectionMade(self)
		#self.logger = MessageLogger(open(self.factory.filename, "a"))
		#self.logger.log("[connected at %s]" % time.asctime(time.localtime(time.time())))

	def connectionLost(self, reason):
		irc.IRCClient.connectionLost(self, reason)
		#self.logger.log("[disconnected at %s]" % time.asctime(time.localtime(time.time())))
		#self.logger.close()

	# callbacks for events

	def signedOn(self):
		"""Called when bot has succesfully signed on to server."""
		self.join(self.factory.channel)

	def joined(self, channel):
		"""This will get called when the bot joins the channel."""
		#self.logger.log("[I have joined %s]" % channel)
		self.msg(channel, "I am %s, I try to help remind %s about his todo list." % (self.nickname, self.jmw))
		self.msg(channel, "Use: %s: %s <msg> and I will remind %s when I see him." % (self.nickname, self.remind, self.jmw))
		self.msg(channel, "/msg %s %s <msg> and I will remind %s _privately_ when I see him." % (self.nickname, self.remind, self.jmw))
		self.msg(channel, "The @list command will list all queued reminders for %s." % self.jmw)
		self.msg(channel, "The @about command will tell you about %s." % self.nickname)

	def privmsg(self, user, channel, msg):
		"""This will get called when the bot receives a message."""
		user = user.split('!', 1)[0]

		# Check to see if JMW is talking in channel
		if user == self.jmw:
			delta = time.time() - self.lastseenat	# time elapsed
			if len(self.reminders) > 0:	# only if there's stuff...
				self.lastseenat = time.time()		# i saw him !
				self.store.write('lastseenat', self.lastseenat)	# save

			if delta > self.delta:	# haven't seen him in a while!
				# for each public message
				empty = True
				public_empty = True
				private_empty = True
				# TODO: sort by oldest first
				for x in self.reminders:
					empty = False
					if x.get('type', None) == 'public':
						public_empty = False
						self.msg(channel, "%s: @%d %s reminded you to: %s [%d sec(s) ago]" % (self.jmw, x.get('id', -1), x.get('from', '<unknown>'), x.get('msg', '<?>'), time.time()-x.get('time', time.time())))
					elif x.get('type', None) == 'private':
						private_empty = False
						self.msg(user, "@%d %s reminded you to: %s [%d sec(s) ago]" % (x.get('id', -1), x.get('from', '<unknown>'), x.get('msg', '<?>'), time.time()-x.get('time', time.time())))

				if not public_empty:
					self.msg(channel, "%s: Use: %s: %s <id> to set task as done." % (self.jmw, self.nickname, self.done))
				if not private_empty:
					self.msg(user, "Use: %s <id> to set task as done." % self.done)

		# Check to see if they're sending me a private message
		if channel == self.nickname:
			if msg.startswith(self.remind+' '):
				reminder = msg[len(self.remind+' '):]

				# append private reminder
				self.maxid = self.maxid + 1	# increment
				# TODO: add more data to reminders ?
				self.reminders.append({'id': self.maxid, 'msg': reminder, 'from': user, 'time': time.time(), 'type': 'private'})
				self.store.write('maxid', self.maxid)	# save
				self.store.write('reminders', self.reminders)	# save
				self.msg(user, "Okay, I'll remind %s privately when I see him." % self.jmw)
				return

			if msg.startswith(self.list) and user == self.jmw:
				empty = True
				# TODO: sort by oldest first
				for x in self.reminders:
					empty = False
					if x.get('type', None) == 'public':
						self.msg(user, "@%d %s reminded you to: %s [public, %d sec(s) ago]" % (x.get('id', -1), x.get('from', '<unknown>'), x.get('msg', '<?>'), time.time()-x.get('time', time.time())))
					elif x.get('type', None) == 'private':
						self.msg(user, "@%d %s reminded you to: %s [private, %d sec(s) ago]" % (x.get('id', -1), x.get('from', '<unknown>'), x.get('msg', '<?>'), time.time()-x.get('time', time.time())))

				if not empty:
					self.msg(user, "Use: %s <id> to set task as done." % self.done)
				else:
					self.msg(user, "Yay! You have no tasks! (Maybe database is broken?)")

				return

			# remove messages when messaged privately by jmw
			if msg.startswith(self.done+' ') and user == self.jmw:
				remainder = msg[len(self.done+' '):]

				try:
					remainder = int(remainder)
				except ValueError, e:
					self.msg(channel, "%s: Please specify a valid message id." % user)
					return

				# delete reminder
				found = -1
				for i in range(len(self.reminders)):
					if self.reminders[i].get('id', -1) == remainder:
						found = i

				if found < 0:
					self.msg(user, "Can't find message! [id %d]." % remainder)
					return

				delete = self.reminders[found]
				del self.reminders[found]
				self.msg(user, "Okay, reminder [id %d] was removed." % delete.get('id', -1))
				self.msg(delete.get('from', user), "Reminder [id %d; %s] was removed by %s." % (delete.get('id', -1), delete.get('msg', '<?>'), self.jmw))
				self.store.write('reminders', self.reminders)	# save
				return

			if msg.startswith(self.about):
				self.msg(user, "The %s was written by @purpleidea. https://ttboj.wordpress.com/" % self.nickname)
				return

			self.msg(user, "Sorry, I can't help you with that!")
			return

		# Otherwise check to see if it is a message directed at me
		if msg.startswith(self.nickname+":"+' '):
			msg = msg[len(self.nickname+': '):]	# remove prefix
			if msg.startswith(self.remind+' '):
				reminder = msg[len(self.remind+' '):]
				self.maxid = self.maxid + 1	# increment
				# TODO: add more data to reminders ?
				self.reminders.append({'id': self.maxid, 'msg': reminder, 'from': user, 'time': time.time(), 'type': 'public'})
				self.store.write('maxid', self.maxid)	# save
				self.store.write('reminders', self.reminders)	# save
				self.msg(channel, "%s: Okay, I'll remind %s when I see him. [id: %d]" % (user, self.jmw, self.maxid))
				return

			if msg.startswith(self.list):
				empty = True
				public_empty = True
				private_empty = True
				# TODO: sort by oldest first
				for x in self.reminders:
					empty = False
					if x.get('type', None) == 'public':
						self.msg(channel, "@%d %s reminded %s to: %s [%d sec(s) ago]" % (x.get('id', -1), x.get('from', '<unknown>'), self.jmw, x.get('msg', '<?>'), time.time()-x.get('time', time.time())))
						public_empty = False
					elif x.get('type', None) == 'private' and user == self.jmw:	# only jmw can request the private list
						self.msg(user, "@%d %s reminded you to: %s [private, %d sec(s) ago]" % (x.get('id', -1), x.get('from', '<unknown>'), x.get('msg', '<?>'), time.time()-x.get('time', time.time())))
						private_empty = False


				if not public_empty:
					if user == self.jmw:
						self.msg(channel, "%s: Use: %s: %s <id> to set task as done." % (user, self.nickname, self.done))
				else:
					self.msg(channel, "%s: Yay! %s has no public tasks! (Maybe database is broken?)" % (user, self.jmw))

				if user == self.jmw:
					if not private_empty:
						self.msg(user, "Use: %s <id> to set task as done." % self.done)
					else:
						self.msg(user, "Yay! You have no private tasks! (Maybe database is broken?)")

				return

			# remove finished reminder, only if asked to by jmw
			if msg.startswith(self.done+' ') and user == self.jmw:
				remainder = msg[len(self.done+' '):]

				try:
					remainder = int(remainder)
				except ValueError, e:
					self.msg(channel, "%s: Please specify a valid message id." % user)
					return

				# delete reminder
				found = -1
				for i in range(len(self.reminders)):
					if self.reminders[i].get('id', -1) == remainder:
						found = i

				if found < 0:
					self.msg(channel, "%s: Can't find message! [id %d]." % (user, remainder))
					return

				delete = self.reminders[found]
				del self.reminders[found]
				self.msg(channel, "%s: Okay, reminder [id %d] was removed." % (user, delete.get('id', -1)))
				self.msg(delete.get('from', channel), "Reminder [id %d; %s] was removed by %s." % (delete.get('id', -1), delete.get('msg', '<?>'), self.jmw))
				self.store.write('reminders', self.reminders)	# save
				return

			if msg.startswith(self.about):
				self.msg(channel, "%s: The %s was written by @purpleidea. https://ttboj.wordpress.com/" % (user, self.nickname))
				return

			self.msg(channel, "%s: Sorry, I can't help you with that!" % user)
			return

	def action(self, user, channel, msg):
		"""This will get called when the bot sees someone do an action."""
		user = user.split('!', 1)[0]
		#self.logger.log("* %s %s" % (user, msg))

	# irc callbacks

	def irc_NICK(self, prefix, params):
		"""Called when an IRC user changes their nickname."""
		old_nick = prefix.split('!')[0]
		new_nick = params[0]
		#self.logger.log("%s is now known as %s" % (old_nick, new_nick))


	# For fun, override the method that determines how a nickname is changed on
	# collisions. The default method appends an underscore.
	def alterCollidedNick(self, nickname):
		"""
		Generate an altered version of a nickname that caused a collision in an
		effort to create an unused related name for subsequent registration.
		"""
		return nickname + '^'



class BotFactory(protocol.ClientFactory):
	"""A factory for bots.

	A new protocol instance will be created each time we connect to the server.
	"""

	# the JMWbot hangs out in #gluster
	def __init__(self, channel='gluster', filename='jmwbot.dat'):
		self.channel = channel
		self.filename = filename

	def buildProtocol(self, addr):
		# create persistent data store
		s = Store(filename=self.filename)
		p = JMWBot(store=s)
		p.factory = self
		return p

	def clientConnectionLost(self, connector, reason):
		"""If we get disconnected, reconnect to server."""
		connector.connect()

	def clientConnectionFailed(self, connector, reason):
		print "connection failed:", reason
		reactor.stop()


if __name__ == '__main__':
	# initialize logging
	log.startLogging(sys.stdout)

	# create factory protocol and application
	#f = BotFactory(sys.argv[1], sys.argv[2])
	f = BotFactory()

	# connect factory to this host and port
	reactor.connectTCP("irc.freenode.net", 6667, f)

	# run bot
	reactor.run()

