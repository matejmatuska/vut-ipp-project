import re
import sys
from enum import Enum, auto
import xml.etree.ElementTree as ET

RESULT_OK = 0
RESULT_ERR_ARGUMENTS = 10
RESULT_ERR_OPENING_INFILES = 11
RESULT_ERR_OPENING_OUTFILES = 12

RESULT_ERR_XML_FORMAT = 31
RESULT_ERR_XML_STRUCTURE = 32

RESULT_ERR_SEMANTICS = 52 # var redefinition, undefined label
RESULT_ERR_TYPE_COMPAT = 53
RESULT_ERR_UNDEFINED_VAR = 54
RESULT_ERR_FRAME_NONEXISTENT = 55
RESULT_ERR_MISSING_VALUE = 56
RESULT_ERR_INVALID_OPERAND = 57
RESULT_ERR_STRING_MANIPULATION = 58

RESULT_ERR_INTERNAL = 99

def eprint(*objects, sep=' ', end='\n', flush=False):
    print(*objects, sep=sep, end=end, file=sys.stderr, flush=flush)


inputf = None
sourcef = None

for arg in sys.argv:
    arg = arg.split("=", 2)

    if arg[0] == "interpret.py" or arg[0] == "./interpret.py":
        pass # no-op
    elif arg[0] == "--help":
        # TODO print help
        exit(RESULT_OK);

    elif arg[0] == "--source":
        if len(arg) == 1:
            exit(RESULT_ERR_ARGUMENTS)
        sourcef = arg[1]

    elif arg[0] == "--input":
        if len(arg) == 1:
            exit(RESULT_ERR_ARGUMENTS)
        inputf = arg[1]
    else:
        eprint("Unrecognized argument:",  arg[0]);
        exit(RESULT_ERR_ARGUMENTS)


if inputf is None and sourcef is None:
    eprint("Argument --input and/or --source must be specified")
    exit(RESULT_ERR_ARGUMENTS)

if sourcef is None:
    sourcef = sys.stdin

# !!! we must parse the XML tree before changing sys.stdin
try:
    xmltree = ET.parse(sourcef)
except FileNotFoundError:
    eprint("Source file does not exist:", sourcef)
    exit(RESULT_ERR_OPENING_INFILES)
except ET.ParseError:
    eprint("Failed parsing XML")
    exit(RESULT_ERR_XML_FORMAT)

if inputf is not None:
    sys.stdin = open(inputf, 'r')

class Type(Enum):
    INT = auto()
    STRING = auto()
    BOOL = auto()
    NIL = auto()
    VAR = auto()
    LABEL = auto()
    TYPE = auto()
    UNDEF = auto() # variable is declared, but not initialized

class TypedValue:

    def __init__(self, type: Type, value):
        self.value = value
        self.type = type

    def __str__(self):
        return f'TypedValue[type={self.type}, value={self.value}]'

    def __eq__(self, other):
        if not isinstance(other, TypedValue):
            return False

        if self.type == Type.NIL or other.type == Type.NIL:
            return True
        elif self.type == other.type:
            return self.value == other.value
        else:
            return False


class Instruction:
    def __init__(self, opcode, order, args):
        self.opcode = opcode
        self.order = order
        self.args = args


# parse instruction from xml element
def xml_parse_instruction(xml_instr):
    if 'opcode' in xml_instr.attrib:
        opcode = xml_instr.attrib['opcode']
    else:
        exit(RESULT_ERR_XML_STRUCTURE)

    if 'order' in xml_instr.attrib:
        try:
            order = int(xml_instr.attrib['order'])
        except ValueError:
            eprint('Instruction attribute "order" must be positive integer')
            exit(RESULT_ERR_XML_STRUCTURE)
    else:
        exit(RESULT_ERR_XML_STRUCTURE)

    if order <= 0:
        eprint('Attribute "order" must be a positive number, was:', order)
        exit(RESULT_ERR_XML_STRUCTURE)

    xml_args = sorted(xml_instr.iter(), key=lambda child: child.tag);

    args = []
    for arg in xml_args:
        if (xml_instr == arg):
            # iteration over xml element iterates throught itself
            # so we need to skip it
            continue

        arg = xml_parse_arg(arg)
        args.append(arg)

    return Instruction(opcode, order, args)

# Parse argument from xml element
def xml_parse_arg(arg):
    type = arg.attrib['type']
    value = arg.text

    tags = ['arg1', 'arg2', 'arg3']
    if arg.tag not in tags:
        exit(RESULT_ERR_XML_STRUCTURE)

    if type == 'int':
        try:
            value = int(value)
        except ValueError:
            exit(RESULT_ERR_XML_STRUCTURE)

    elif type == 'bool':
        if value == "true":
            value = True;
        else:
            value = False;

    elif type == 'string':
        if value is None:
            value = ''
        else:
            def repl(match):
                x = match.group(0)
                h = '\\x{:02x}'.format(int(x[2:]))
                return h.encode().decode('unicode-escape')

            regex = r"\\\d\d\d"
            value = re.sub(regex, repl, value)

    elif type == 'nil':
        value = 'nil'

    # TODO
    return TypedValue(Type[type.upper()], value)


# Returns address of the label or exits with an error
def jump(labelmap, label):
    if label in labelmap:
        return labelmap[label]
    else:
        eprint("JUMP: Undefined label: ", label)
        exit(RESULT_ERR_SEMANTICS)


# Implementation of DEFVAR instruction
# Exits with error if variable is already defined
def exec_defvar(arg, framestack, tempframe):
    (frame_id, name) = tuple(arg.value.split('@', 2))

    if frame_id == 'GF':
        frame = framestack[0]
    elif frame_id == 'LF':
        if len(framestack) == 1:
            exit(RESULT_ERR_FRAME_NONEXISTENT)
        frame = framestack[-1]
    elif frame_id == 'TF':
        if tempframe is None:
            exit(RESULT_ERR_FRAME_NONEXISTENT)
        frame = tempframe
    else:
        # should not happen, but must be handled in python, parsers job
        eprint("Should not happen, parsers job!")
        exit(RESULT_ERR_INTERNAL)

    if name in frame:
        eprint('DEFVAR variable is already defined: ', arg.value)
        exit(RESULT_ERR_SEMANTICS)

    frame[name] = TypedValue(Type.UNDEF, None)


# Implementation of EXIT instruction
def exec_exit(exit_code):
    eprint(exit_code)
    if exit_code.value is None:
        exit(RESULT_ERR_MISSING_VALUE)

    if exit_code.type != Type.INT:
        eprint("EXIT: exit code must be an integer")
        exit(RESULT_ERR_TYPE_COMPAT)

    if exit_code.value < 0 or exit_code.value > 49:
        eprint("EXIT: error code out of range")
        exit(RESULT_ERR_INVALID_OPERAND)

    exit(exit_code.value)


def exec_binary(instr, op, frames):
    """
    Executes binary instruction

    Instruction arguments must have the following types:
    [variable, symbol, symbol]

    Paramaters
    ----------

    instr : Instruction
        The instruction
    op :
        Implementation of instruction
    framestack :
        Stack of frames
    tempframe :
        Temporary frame
    """
    dest, a, b = tuple(instr.args)

    dest = frames.get_var(dest)
    a = frames.resolve_symbol(a)
    b = frames.resolve_symbol(b)

    op(dest, a, b)


def are_eq(sym1, sym2, frames):
    sym1 = frames.resolve_symbol(sym1, frames)
    sym2 = frames.resolve_symbol(sym2, frames)

    if sym1.type == Type.NIL and sym2.type == Type.NIL:
        return True
    elif sym1.type == Type.NIL or sym2.type == Type.NIL:
        return False
    elif sym1.type == sym2.type:
        return sym1.value == sym2.value
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_read(dest, type):

    try:
        i = input()
    except EOFError:
        dest.type = Type.NIL
        dest.value = Type.NIL
        return

    if type == Type.INT:
        dest.type = Type.INT
        try:
            dest.value = int(i)
        except ValueError:
            dest.type = Type.NIL
            dest.value = Type.NIL

    elif type == Type.STRING:
        dest.type = Type.STRING
        dest.value = i

    elif type == Type.BOOL:
        dest.type = Type.BOOL
        dest.value = i.casefold() == 'true'
    else:
        eprint("READ: Can't read values of type: ", type)
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_write(arg):
    if arg.type == Type.BOOL:
        if arg.value == True:
            print("true", end='')
        else:
            print("false", end='')
    elif arg.type == Type.NIL:
        pass
    elif isinstance(arg.value, Type):
        if (arg.value != Type.UNDEF):
            print(arg.value.name.lower(), end='')
    else:
        print(arg.value, end='')


def exec_concat(dest, sym1, sym2):
    if sym1.type == Type.STRING and sym2.type == Type.STRING:
        dest.type = Type.STRING
        dest.value = sym1.value + sym2.value
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_stri2int(dest, sym1, sym2):
    if sym1.type == Type.STRING and sym2.type == Type.INT:

        if sym2.value >= len(sym1.value) or sym2.value < 0:
            exit(RESULT_ERR_STRING_MANIPULATION)

        char = sym1.value[sym2.value]
        dest.type = Type.INT
        dest.value = ord(char)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_int2char(dest, symb):
    if symb.type == Type.INT:
        dest.type = Type.STRING
        try:
            dest.value = chr(symb.value)
        except ValueError:
            exit(RESULT_ERR_STRING_MANIPULATION)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_getchar(dest, sym1, sym2):
    if sym1.type == Type.STRING and sym2.type == Type.INT:
        if sym2.value >= len(sym1.value) or sym2.value < 0:
            exit(RESULT_ERR_STRING_MANIPULATION)

        dest.type = Type.STRING
        dest.value = sym1.value[sym2.value]
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_setchar(dest, sym1, sym2):
    if (dest.value == None):
        exit(RESULT_ERR_MISSING_VALUE)
    elif (dest.type == Type.STRING and sym1.type == Type.INT
            and sym2.type == Type.STRING):

        if (sym1.value >= len(dest.value) or sym1.value < 0
                or len(sym2.value) == 0):
            exit(RESULT_ERR_STRING_MANIPULATION)

        s = dest.value
        string = s[:sym1.value] + sym2.value[0] + s[sym1.value + 1:]
        # type is already string
        dest.value = string
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_artihmetic(instr, frames, operation):
    def op(dest, a, b):
        if a.type == Type.INT and b.type == Type.INT:
            dest.type = Type.INT
            dest.value = operation(a.value, b.value)
        else:
            exit(RESULT_ERR_TYPE_COMPAT)

    exec_binary(instr, op, frames)


def exec_relational(instr, frames, operation):
    dest, sym1, sym2 = tuple(instr.args)

    sym1 = frames.resolve_symbol(sym1)
    sym2 = frames.resolve_symbol(sym2)

    dest = frames.get_var(dest)
    dest.type = Type.BOOL
    dest.value = operation(sym1, sym2)


def exec_logical(instr, frames, operation):
    dest, sym1, sym2 = tuple(instr.args)

    sym1 = frames.resolve_symbol(sym1)
    sym2 = frames.resolve_symbol(sym2)

    if sym1.type == Type.BOOL and sym2.type == Type.BOOL:
        dest = frames.get_var(dest)
        dest.type = Type.BOOL
        dest.value = operation(sym1.value, sym2.value)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


root = xmltree.getroot()
if root.tag != "program":
    exit(RESULT_ERR_XML_STRUCTURE)

instructions = []
for elem in root.findall('./'):
    if elem.tag != 'instruction':
        exit(RESULT_ERR_XML_STRUCTURE)
    instr = xml_parse_instruction(elem)
    instructions.append(instr)

instructions.sort(key=lambda instr: instr.order)

class Frames:
    def __init__(self):
        self.framestack = []
        self.framestack.append({}) # add global frame
        self.tempframe = None

    def defvar(self, var):
        (frame_id, name) = tuple(var.value.split('@', 2))

        if frame_id == 'GF':
            frame = self.framestack[0]
        elif frame_id == 'LF':
            if len(self.framestack) == 1:
                exit(RESULT_ERR_FRAME_NONEXISTENT)
            frame = self.framestack[-1]
        elif frame_id == 'TF':
            if self.tempframe is None:
                exit(RESULT_ERR_FRAME_NONEXISTENT)
            frame = self.tempframe
        else:
            # should not happen, but must be handled in python
            # parsers job
            eprint("Should not happen, parsers job!")
            exit(RESULT_ERR_INTERNAL)

        if name in frame:
            eprint('DEFVAR variable is already defined: ', var.value)
            exit(RESULT_ERR_SEMANTICS)

        frame[name] = TypedValue(Type.UNDEF, None)


    def get_var(self, var):
        (frame_id, name) = tuple(var.value.split('@', 2))

        if frame_id == 'GF':
            frame = self.framestack[0]
        elif frame_id == 'LF':
            if len(self.framestack) == 1:
                eprint("No LF available")
                exit(RESULT_ERR_FRAME_NONEXISTENT)
            frame = self.framestack[-1]
        elif frame_id == 'TF':
            if self.tempframe is None:
                eprint("TF is not initialized")
                exit(RESULT_ERR_FRAME_NONEXISTENT)
            frame = self.tempframe
        else:
            exit(7) # TODO

        if name not in frame:
            exit(RESULT_ERR_UNDEFINED_VAR)

        return frame[name]

    def resolve_symbol(self, symb, require_set = True):
        """
        If symbol is a variable resolves it to its actual value and type
        """
        if symb.type == Type.VAR:
            symb = self.get_var(symb)
            if require_set and symb.value is None:
                exit(RESULT_ERR_MISSING_VALUE)
        return symb

    def pushlocal(self):
        if self.tempframe is None:
            exit(RESULT_ERR_FRAME_NONEXISTENT)

        self.framestack.append(self.tempframe)
        self.tempframe = None

    def poplocal(self):
        if len(self.framestack) == 1:
            eprint("POPFRAME: No available LF")
            exit(RESULT_ERR_FRAME_NONEXISTENT)

        self.tempframe = self.framestack.pop()

    def create_frame(self):
        self.tempframe = {}



datastack = []
callstack = []
labelmap = {}

pc = 0 # program counter
prev_order = -1
while pc < len(instructions):
    instr = instructions[pc]
    if instr.order == prev_order:
        exit(RESULT_ERR_XML_STRUCTURE)
    prev_order = instr.order

    pc = pc + 1

    if instr.opcode == 'LABEL':
        label = instr.args[0].value
        if label in labelmap:
            exit(RESULT_ERR_SEMANTICS)
        labelmap[label] = pc

frames = Frames()
pc = 0
while pc < len(instructions):
    instr: Instruction = instructions[pc]
    pc = pc + 1

    if "DEFVAR" == instr.opcode:
        frames.defvar(instr.args[0])

    elif "MOVE" == instr.opcode:
        dest = instr.args[0]
        src = instr.args[1]

        if (src.value == None):
            src.value = ''

        dest = frames.get_var(dest)
        if dest is None:
            exit(RESULT_ERR_UNDEFINED_VAR)

        src = frames.resolve_symbol(src)
        dest.type = src.type
        dest.value = src.value

    elif "LABEL" == instr.opcode:
        # labels are processed before execution loop
        pass

    elif "CALL" == instr.opcode:
        callstack.append(pc)
        label = instr.args[0].value
        pc = jump(labelmap, label)

    elif "RETURN" == instr.opcode:
        if not callstack:
            eprint('RETURN: Callstack is empty')
            exit(RESULT_ERR_MISSING_VALUE)
        pc = callstack.pop()

    elif "EXIT" == instr.opcode:
        exit_code = frames.resolve_symbol(instr.args[0])
        exec_exit(exit_code)

    elif "CREATEFRAME" == instr.opcode:
        frames.create_frame()

    elif "PUSHFRAME" == instr.opcode:
        frames.pushlocal()

    elif "POPFRAME" == instr.opcode:
        frames.poplocal()

    elif "JUMP" == instr.opcode:
        label = instr.args[0].value
        pc = jump(labelmap, label)

    elif "JUMPIFEQ" == instr.opcode:
        label, sym1, sym2 = tuple(instr.args)
        addr = jump(labelmap, label.value)
        if are_eq(sym1, sym2, frames):
            pc = addr

    elif "JUMPIFNEQ" == instr.opcode:
        label, sym1, sym2 = tuple(instr.args)
        addr = jump(labelmap, label.value)
        if not are_eq(sym1, sym2, frames):
            pc = addr

    elif "READ" == instr.opcode:
        dest, type = tuple(instr.args)
        dest = frames.get_var(dest)
        exec_read(dest, Type[type.value.upper()])

    elif "WRITE" == instr.opcode:
        arg = frames.resolve_symbol(instr.args[0])
        exec_write(arg)

    elif "CONCAT" == instr.opcode:
        exec_binary(instr, exec_concat, frames)

    elif "STRLEN" == instr.opcode:
        dest, symb = tuple(instr.args)
        symb = frames.resolve_symbol(symb)

        if symb.type != Type.STRING:
            exit(RESULT_ERR_TYPE_COMPAT)

        dest = frames.get_var(dest)
        dest.type = Type.INT
        dest.value = len(symb.value)

    elif "GETCHAR" == instr.opcode:
        exec_binary(instr, exec_getchar, frames)

    elif "SETCHAR" == instr.opcode:
        exec_binary(instr, exec_setchar, frames)

    elif "TYPE" == instr.opcode:
        dest, symb = tuple(instr.args)

        symb = frames.resolve_symbol(symb, require_set=False)
        if symb.value is None:
            symb.type = Type.UNDEF

        dest = frames.get_var(dest)
        # THIS MUST BE CALLED IN THIS ORDER
        # because dest and symb might resolve to the same variable
        dest.value = symb.type
        dest.type = Type.STRING

    elif "PUSHS" == instr.opcode:
        symb = frames.resolve_symbol(instr.args[0])
        datastack.append(symb)

    elif "POPS" == instr.opcode:
        if not datastack:
            exit(RESULT_ERR_MISSING_VALUE)

        dest = instr.args[0]
        dest = frames.get_var(dest)
        item = datastack.pop()
        dest.type = item.type
        dest.value = item.value

    elif "ADD" == instr.opcode:
        exec_artihmetic(instr, frames, lambda a, b: a + b)
    elif "SUB" == instr.opcode:
        exec_artihmetic(instr, frames, lambda a, b: a - b)
    elif "MUL" == instr.opcode:
        exec_artihmetic(instr, frames, lambda a, b: a * b)
    elif "IDIV" == instr.opcode:
        def op(dest, a, b):
            if b.type == Type.INT and b.value == 0:
                exit(RESULT_ERR_INVALID_OPERAND)
            if a.type == Type.INT and b.type == Type.INT:
                dest.type = Type.INT
                dest.value = a.value // b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)

        exec_binary(instr, op, frames)

    elif "LT" == instr.opcode:
        def lt(a, b):
            if a.type == b.type and a.type != Type.NIL:
                return a.value < b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)
        exec_relational(instr, frames, lt)

    elif "GT" == instr.opcode:
        def gt(a, b):
            if a.type == b.type and a.type != Type.NIL:
                return a.value > b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)
        exec_relational(instr, frames, gt)

    elif "EQ" == instr.opcode:
        def eq(a, b):
            if a.type == Type.NIL and b.type == Type.NIL:
                return True
            elif a.type == Type.NIL or b.type == Type.NIL:
                return False
            if a.type == b.type:
                return a.value == b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)

        exec_relational(instr, frames, eq)
    elif "AND" == instr.opcode:
        exec_logical(instr, frames, lambda a, b: a and b)
    elif "OR" == instr.opcode:
        exec_logical(instr, frames, lambda a, b: a or b)
    elif "NOT" == instr.opcode:
        dest, symb = tuple(instr.args)
        symb = frames.resolve_symbol(symb)

        if symb.type == Type.BOOL:
            dest = frames.get_var(dest)
            dest.type = Type.BOOL
            dest.value = not symb.value
        else:
            exit(RESULT_ERR_TYPE_COMPAT)

    elif "INT2CHAR" == instr.opcode:
        dest, symb = tuple(instr.args)
        symb = frames.resolve_symbol(symb)
        dest = frames.get_var(dest)
        exec_int2char(dest, symb)

    elif "STRI2INT" == instr.opcode:
        exec_binary(instr, exec_stri2int, frames)

    elif "DPRINT" == instr.opcode:
        symb = frames.resolve_symbol(instr.args[0])
        eprint(symb.value)

    elif "BREAK" == instr.opcode:
        # TODO maybe BREAK
        pass
    else:
        eprint("Invalid opcode: ", instr.opcode)
        exit(RESULT_ERR_XML_STRUCTURE)

