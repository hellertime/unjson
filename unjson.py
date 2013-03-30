#!/usr/bin/env python

import re

class TDOP(object):
	"""Top-Down Op Precedence Parser Generator (http://effbot.org/zone/simple-top-down-parsing.htm)"""
	PATTERN = re.compile("")
	NAME = object()
	LITERAL = object()
	END = object()
	class base(object):
		"""base class of all symbols"""
		id = None                     # node/token type name
		pattern = None                # regex pattern describing this token
		value = None                  # literal value (if any)
		first = second = third = None # parse tree node branching

		def nud(self): raise SyntaxError("Syntax error (%r)" % self.id) # null context stub
		def led(self, left): raise SyntaxError("Syntax error (%r)" % self.id) # left context stub
		def __repr__(self):
			rmap = {TDOP.NAME: "name", TDOP.LITERAL: "literal"}
			if self.id == TDOP.END:
				return "(end)"
			elif self.id == TDOP.NAME or self.id == TDOP.LITERAL:
				return "(%s %s)" % (rmap[self.id], self.value)
			return "(" + " ".join([str(s) for s in [self.id,self.first,self.second,self.third] if s is not None]) + ")"
	
	def __init__(self):
		self.token = None
		self.symbol(TDOP.END)
	
	SYMBOL_TABLE = {}
	def symbol(self, id, bp=0, name=None):
		"""token factory"""
		try:
			s = self.SYMBOL_TABLE[id]
		except KeyError:
			class s(TDOP.base):
				pass
			if isinstance(id, type(TDOP.PATTERN)):
				assert(name is not None)
				s.__name__ = "symbol-" + name 
				s.id = name
				s.pattern = id
				s.nud = lambda self: self
			elif id == TDOP.END:
				s.__name__ = "symbol-end"
				s.id = TDOP.END
				s.pattern = None
				s.value = None
			else:
				s.__name__ = "symbol-" + id
				s.id = id
				s.pattern = re.compile(re.escape(id))
			s.lbp = bp # sets the left binding power for this symbol
			self.SYMBOL_TABLE[id] = s
		else:
			s.lbp = max(bp, s.lbp) # updates the symbols left binding power
		return s
	
	def symbols(self):
		return ((id,self.SYMBOL_TABLE[id]) for id in self.SYMBOL_TABLE if id != TDOP.END)
	
	def expression(self, rbp=0):
		"""main parse driver"""
		t = self.token
		self.token = self.next_token()
		left = t.nud()
		while rbp < self.token.lbp:
			t = self.token
			self.token = self.next_token()
			left = t.led(left)
		return left
	
	def parse(self, input):
		self.next_token = self.tokenize(input).__next__
		self.token = self.next_token()
		return self.expression()
	
	def tokenize(self, input):
		raise NotImplemented("Yout must provide an implementation of TDOP.tokenize(self, input)")
	
	def advance(self, id=None):
		"""helper function to skip to expected token"""
		if id and self.token.id != id:
			raise SyntaxError("Expected %r. Currently: %r" % (id, self.token.id))
		self.token = self.next_token()
	
	@staticmethod
	def bind(s):
		"""decorator, binds method to symbol"""
		assert(issubclass(s, TDOP.base))
		def _bind(f):
			setattr(s, f.__name__, f)
		return _bind
	
	def constant(self, s):
		@self.bind(self.symbol(s))
		def nud(self):
			self.id = TDOP.LITERAL
			self.value = id
			return self
	
class UNJSON(TDOP):
	def __init__(self):
		TDOP.__init__(self)
		self.symbol(re.compile(r"""# capture a json number
					-?                # optional leading minus
					(0|[1-9][0-9]*)   # allow a single zero, but no leading zeros
					(?:\.[0-9]+)?     # optional fractional part
					(?:[eE]           # optional scientific part
					   [+-]?          #   optional sinage
					   [0-9]+)?       #   exponent
					""", re.VERBOSE), name="jsonNumber")
		self.symbol(re.compile(r"""# capture a json string
					"                     # strings must start with a "
					# capture the string inside the quotes
					(( \\"               # quotation mark
					|  \\\\              # reverse solidus
					|  \\/               # solidus
					|  \\b               # backspace
					|  \\f               # formfeed
					|  \\n               # newline
					|  \\r               # carriage return
					|  \\t               # htab
					| [^"])*?)           # anything else
					"
					""", re.VERBOSE | re.UNICODE), name="jsonString")

		self.constant("null")
		self.constant("false")
		self.constant("true")

		self.symbol(",")

		self.symbol("]")
		@TDOP.bind(self.symbol("["))
		def nud(self):
			self.first = []
			if self.parser.token.id != "]":
				while 1:
					if self.parser.token.id == "]":
						break
					self.first.append(self.parser.expression())
					if self.parser.token.id != ",":
						break
					self.parser.advance(",")
			self.parser.advance("]")
			return self

		self.symbol(":")

		self.symbol("}")
		@TDOP.bind(self.symbol("{"))
		def nud(self):
			self.first = []
			if self.parser.token.id != "}":
				while 1:
					if self.parser.token.id == "}":
						break
					self.first.append(self.parser.expression())
					self.parser.advance(":")
					self.first.append(self.parser.expression())
					if self.parser.token.id != ",":
						break;
					self.parser.advance(",")
			self.parser.advance("}")
			return self
	
	def tokenize(self, input):
		input = input.lstrip()
		while input:
			for id, s in self.symbols():
				match = s.pattern.match(input)
				if match:
					sym = s()
					sym.parser = self
					if s.__name__ == "symbol-jsonString":
						sym.value = match.group(1)
					else:
						sym.value = match.group(0)	

					yield sym
					input = input[match.end():].lstrip()
					break
			else:
				raise SyntaxError("Unknown Input: " + input[:32])
		yield self.symbol(TDOP.END)
	
	def decode_atom(self, node):
		if node.id == "null":
			return None
		elif node.id == "true":
			return True
		elif node.id == "false":
			return False
		elif node.id == "jsonString":
			return str(node.value)
		elif node.id == "jsonNumber":
			return eval(node.value) # we've already syntax checked that this is a numeric
		else:
			raise ValueError("Non-atomic Value: (%r)" % node.id)
	
	def decode_list(self, node):
		l = []
		return [self.decode(x) for x in node.first]
	
	def decode_object(self, node):
		o = {}
		l = iter(node.first)
		for key in l:
			assert key.id == "jsonString", "JSON object keys must be strings"
			value = next(l)
			o[str(key.value)] = self.decode(value)

		return o
	
	def decode(self, node):
		if node.id == "{":
			return self.decode_object(node)
		elif node.id == "[":
			return self.decode_list(node)
		else:
			return self.decode_atom(node)
	
	def parse(self, input):
		tree = TDOP.parse(self, input)
		assert tree.id == "{", "JSON data must be an object"
		return self.decode_object(tree)

if __name__ == '__main__':
	json = """{
    "firstName": "John",
    "lastName": "Smith",
    "age": 25,
    "address": {
        "streetAddress": "21 2nd Street",
        "city": "New York",
        "state": "NY",
        "postalCode": 10021
    },
    "phoneNumbers": [
        {
            "type": "home",
            "number": "212 555-1234"
        },
        {
            "type": "fax",
            "number": "646 555-4567"
        }
    ]
}"""
	print("JSON:")
	print(json)
	unjson = UNJSON().parse(json)
	print("UNJSON:")
	print(repr(unjson))
