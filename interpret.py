import re
import sys
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

# we must parse the XML tree before changing sys.stdin
try:
    xmltree = ET.parse(sourcef)
except FileNotFoundError:
    eprint("Source file does not exist:", sourcef)
    exit(2) # TODO error code
except ET.ParseError:
    eprint("Failed parsing XML")
    exit(RESULT_ERR_XML_FORMAT)

if inputf is not None:
    sys.stdin = open(inputf, 'r')


class TypedValue:

    def __init__(self, type, value):
        self.value = value
        self.type = type

    def __str__(self):
        return f'TypedValue[type={self.type}, value={self.value}]'

    def __eq__(self, other):
        if not isinstance(other, TypedValue):
            return False

        if self.type == 'nil' or other.type == 'nil':
            return True
        elif self.type == other.type:
            return self.value == other.value
        else:
            return False


class Instruction:

    def __init__(self, opcode, args):
        self.opcode = opcode
        self.args = args


def xml_parse_instruction(xmlInstr):
    if 'opcode' in xmlInstr.attrib:
        opcode = xmlInstr.attrib['opcode']
    else:
        exit(RESULT_ERR_XML_STRUCTURE)

    if 'order' in xmlInstr.attrib:
        # TODO ValueError
        order = int(xmlInstr.attrib['order'])
    else:
        exit(RESULT_ERR_XML_STRUCTURE)

    if order < 0:
        eprint('Attribute "order" must be a positive number, was:', order)
        exit(RESULT_ERR_XML_STRUCTURE)

    args = []
    for arg in xmlInstr.iter():
        if (xmlInstr == arg):
            continue
        # TODO sort
        order, arg = xml_parse_arg(arg)
        args[order] = arg

    return Instruction(opcode, args)


def xml_parse_arg(arg):
    type = arg.attrib['type']
    value = arg.text

    tags = ['arg1', 'arg2', 'arg3']
    if arg.tag not in tags:
        exit(RESULT_ERR_XML_STRUCTURE)

    if type == 'int':
        value = int(value)
    elif type == 'bool':
        if value == "true":
            value = True;
        elif value == "false":
            value = False;
        else:
            # TODO err code
            exit(666)
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

    return arg.tag[:-1], TypedValue(type, value)


def jump(labelmap, label):
    if label in labelmap:
        return labelmap[label]
    else:
        exit(RESULT_ERR_SEMANTICS)


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
        exit(456)

    if name in frame:
        eprint('DEFVAR variable is already defined: ', arg.value)
        exit(RESULT_ERR_SEMANTICS)

    frame[name] = TypedValue(None, None)


def exec_exit(exit_code):
    if exit_code.value is None:
        exit(RESULT_ERR_MISSING_VALUE)

    if exit_code.type != 'int':
        eprint("EXIT: exit code must be an integer")
        exit(RESULT_ERR_TYPE_COMPAT)

    if exit_code.value < 0 or exit_code.value > 49:
        eprint("EXIT: error code out of range")
        exit(RESULT_ERR_INVALID_OPERAND)

    exit(exit_code.value)


def get_var(arg, framestack, tempframe):

    (frame_id, name) = tuple(arg.value.split('@', 2))

    if frame_id == 'GF':
        frame = framestack[0]
    elif frame_id == 'LF':
        if len(framestack) == 1:
            eprint("No LF available")
            exit(RESULT_ERR_FRAME_NONEXISTENT)
        frame = framestack[-1]
    elif frame_id == 'TF':
        if tempframe is None:
            eprint("TF is not initialized")
            exit(RESULT_ERR_FRAME_NONEXISTENT)
        frame = tempframe
    else:
        exit(456)

    if name not in frame:
        exit(RESULT_ERR_UNDEFINED_VAR)

    return frame[name]


def resolve_symbol(symb, framestack, tempframe, require_set = True):
    if symb.type == 'var':
        symb = get_var(symb, framestack, tempframe)
        if require_set and symb.value is None:
            exit(RESULT_ERR_MISSING_VALUE)
    return symb


def exec_binary(instr, op, framestack, tempframe):
    dest, a, b = tuple(instr.args)

    dest = get_var(dest, framestack, tempframe)
    a = resolve_symbol(a, framestack, tempframe)
    b = resolve_symbol(b, framestack, tempframe)

    op(dest, a, b)


def are_eq(sym1, sym2, framestack, tempframe):
    sym1 = resolve_symbol(sym1, framestack, tempframe)
    sym2 = resolve_symbol(sym2, framestack, tempframe)

    if sym1.type == 'nil' and sym2.type == 'nil':
        return True
    elif sym1.type == 'nil' or sym2.type == 'nil':
        return False
    elif sym1.type == sym2.type:
        return sym1.value == sym2.value
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_read(dest, type):

    try:
        i = input()
    except EOFError:
        dest.type = 'nil'
        dest.value = 'nil'
        return

    if type.value == 'int':
        dest.type = 'int'
        try:
            dest.value = int(i)
        except ValueError:
            dest.type = 'nil'
            dest.value = 'nil'

    elif type.value == 'string':
        dest.type = 'string'
        dest.value = i

    elif type.value == 'bool':
        dest.type = 'bool'
        dest.value = i.casefold() == 'true'
    else:
        eprint("READ TODO type:", type)
        # TODO
        pass


def exec_write(arg):
    if arg.type == "bool":
        if arg.value == True:
            print("true", end='')
        else:
            print("false", end='')
    elif arg.type == "nil":
        print('', end='')
    else:
        print(arg.value, end='')


def exec_concat(dest, sym1, sym2):
    if sym1.type == 'string' and sym2.type == 'string':
        dest.type = 'string'
        dest.value = sym1.value + sym2.value
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_stri2int(dest, sym1, sym2):
    if sym1.type == 'string' and sym2.type == 'int':

        if sym2.value >= len(sym1.value) or sym2.value < 0:
            exit(RESULT_ERR_STRING_MANIPULATION)

        char = sym1.value[sym2.value]
        dest.type = 'int'
        dest.value = ord(char)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_int2char(dest, symb):
    if symb.type == 'int':
        dest.type = 'string'
        try:
            dest.value = chr(symb.value)
        except ValueError:
            exit(RESULT_ERR_STRING_MANIPULATION)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_getchar(dest, sym1, sym2):
    if sym1.type == 'string' and sym2.type == 'int':
        if sym2.value >= len(sym1.value) or sym2.value < 0:
            exit(RESULT_ERR_STRING_MANIPULATION)

        dest.type = 'string'
        dest.value = sym1.value[sym2.value]
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_setchar(dest, sym1, sym2):
    if (dest.value == None):
        exit(RESULT_ERR_MISSING_VALUE)
    elif (dest.type == 'string' and sym1.type == 'int'
            and sym2.type == 'string'):

        if (sym1.value >= len(dest.value) or sym1.value < 0
                or len(sym2.value) == 0):
            exit(RESULT_ERR_STRING_MANIPULATION)

        s = dest.value
        string = s[:sym1.value] + sym2.value[0] + s[sym1.value + 1:]
        # type is already string
        dest.value = string
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_artihmetic(instr, framestack, tempframe, operation):
    def op(dest, a, b):
        if a.type == 'int' and b.type == 'int':
            dest.type = 'int'
            dest.value = operation(a.value, b.value)
        else:
            exit(RESULT_ERR_TYPE_COMPAT)

    exec_binary(instr, op, framestack, tempframe)


def exec_relational(instr, framestack, tempframe, operation):
    dest, sym1, sym2 = tuple(instr.args)

    sym1 = resolve_symbol(sym1, framestack, tempframe)
    sym2 = resolve_symbol(sym2, framestack, tempframe)

    dest = get_var(dest, framestack, tempframe)
    dest.type = 'bool'
    dest.value = operation(sym1, sym2)


def exec_logical(instr, framestack, tempframe, operation):
    dest, sym1, sym2 = tuple(instr.args)

    sym1 = resolve_symbol(sym1, framestack, tempframe)
    sym2 = resolve_symbol(sym2, framestack, tempframe)

    if sym1.type == 'bool' and sym2.type == 'bool':
        dest = get_var(dest, framestack, tempframe)
        dest.type = 'bool'
        dest.value = operation(sym1.value, sym2.value)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


root = xmltree.getroot()
if root.tag != "program":
    exit(RESULT_ERR_XML_STRUCTURE)

instructions = list(root.iter("instruction"))
instructions.sort(key=lambda instr: int(instr.attrib['order']))

datastack = []
callstack = []
framestack = []
# add global frame
framestack.append({})
# temporary frame (TF)
tempframe = None

labelmap = {}

pc = 0 # program counter
while pc < len(instructions):
    instr = instructions[pc]
    instructions[pc] = xml_parse_instruction(instr)
    pc = pc + 1

    if instr.attrib['opcode'] == 'LABEL':
        label = instr.find('arg1').text
        if label in labelmap:
            exit(RESULT_ERR_SEMANTICS)
        labelmap[label] = pc

pc = 0
while pc < len(instructions):
    instr: Instruction = instructions[pc]
    #eprint(pc, 'instruction: ' + instr.opcode)
    pc = pc + 1

    if "DEFVAR" == instr.opcode:
        arg = instr.args[0]
        exec_defvar(arg, framestack, tempframe)

    elif "MOVE" == instr.opcode:
        dest = instr.args[0]
        src = instr.args[1]

        if (src.value == None):
            src.value = ''

        dest = get_var(dest, framestack, tempframe)
        if dest is None:
            exit(RESULT_ERR_UNDEFINED_VAR)

        src = resolve_symbol(src, framestack, tempframe)

        dest.type = src.type
        dest.value = src.value

    elif "LABEL" == instr.opcode:
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
        exit_code = instr.args[0]
        exit_code = resolve_symbol(exit_code, framestack, tempframe)

        exec_exit(exit_code)

    elif "CREATEFRAME" == instr.opcode:
        tempframe = {}

    elif "PUSHFRAME" == instr.opcode:
        if tempframe is None:
            exit(RESULT_ERR_FRAME_NONEXISTENT)

        framestack.append(tempframe)
        tempframe = None

    elif "POPFRAME" == instr.opcode:
        if len(framestack) == 1:
            eprint("POPFRAME: No available LF")
            exit(RESULT_ERR_FRAME_NONEXISTENT)

        tempframe = framestack.pop()

    elif "JUMP" == instr.opcode:
        label = instr.args[0].value
        pc = jump(labelmap, label)

    elif "JUMPIFEQ" == instr.opcode:
        label, sym1, sym2 = tuple(instr.args)
        addr = jump(labelmap, label.value)
        if are_eq(sym1, sym2, framestack, tempframe):
            pc = addr

    elif "JUMPIFNEQ" == instr.opcode:
        label, sym1, sym2 = tuple(instr.args)
        addr = jump(labelmap, label.value)
        if not are_eq(sym1, sym2, framestack, tempframe):
            pc = addr

    elif "READ" == instr.opcode:
        dest, type = tuple(instr.args)
        dest = get_var(dest, framestack, tempframe)
        exec_read(dest, type)

    elif "WRITE" == instr.opcode:
        arg = instr.args[0]
        arg = resolve_symbol(arg, framestack, tempframe)
        exec_write(arg)

    elif "CONCAT" == instr.opcode:
        exec_binary(instr, exec_concat, framestack, tempframe)

    elif "STRLEN" == instr.opcode:
        dest, symb = tuple(instr.args)

        symb = resolve_symbol(symb, framestack, tempframe)

        if symb.type != 'string':
            exit(RESULT_ERR_TYPE_COMPAT)

        dest = get_var(dest, framestack, tempframe)
        dest.type = 'int'
        dest.value = len(symb.value)

    elif "GETCHAR" == instr.opcode:
        exec_binary(instr, exec_getchar, framestack, tempframe)

    elif "SETCHAR" == instr.opcode:
        exec_binary(instr, exec_setchar, framestack, tempframe)

    elif "TYPE" == instr.opcode:
        dest, symb = tuple(instr.args)

        symb = resolve_symbol(symb, framestack, tempframe, require_set=False)
        if symb.value is None:
            # if symb is uninitialized variable type is empty string
            symb.type = ''

        dest = get_var(dest, framestack, tempframe)
        # THIS MUST BE CALLED IN THIS ORDER
        # because dest and symb might resolve to the same variable
        dest.value = symb.type
        dest.type = 'string'

    elif "PUSHS" == instr.opcode:
        symb = instr.args[0]

        symb = resolve_symbol(symb, framestack, tempframe)

        datastack.append(symb)

    elif "POPS" == instr.opcode:
        if not datastack:
            exit(RESULT_ERR_MISSING_VALUE)

        dest = instr.args[0]
        dest = get_var(dest, framestack, tempframe)
        item = datastack.pop()
        dest.type = item.type
        dest.value = item.value

    elif "ADD" == instr.opcode:
        exec_artihmetic(instr, framestack, tempframe, lambda a, b: a + b)
    elif "SUB" == instr.opcode:
        exec_artihmetic(instr, framestack, tempframe, lambda a, b: a - b)
    elif "MUL" == instr.opcode:
        exec_artihmetic(instr, framestack, tempframe, lambda a, b: a * b)
    elif "IDIV" == instr.opcode:
        def op(dest, a, b):
            if b.type == 'int' and b.value == 0:
                exit(RESULT_ERR_INVALID_OPERAND)
            if a.type == 'int' and b.type == 'int':
                dest.type = 'int'
                dest.value = a.value // b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)

        exec_binary(instr, op, framestack, tempframe)

    elif "LT" == instr.opcode:
        def lt(a, b):
            if a.type == b.type and a.type != 'nil':
                return a.value < b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)
        exec_relational(instr, framestack, tempframe, lt)
    elif "GT" == instr.opcode:
        def gt(a, b):
            if a.type == b.type and a.type != 'nil':
                return a.value > b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)
        exec_relational(instr, framestack, tempframe, gt)
    elif "EQ" == instr.opcode:
        def eq(a, b):
            if a.type == 'nil' and b.type == 'nil':
                return True
            elif a.type == 'nil' or b.type == 'nil':
                return False
            if a.type == b.type:
                return a.value == b.value
            else:
                exit(RESULT_ERR_TYPE_COMPAT)
        exec_relational(instr, framestack, tempframe, eq)
    elif "AND" == instr.opcode:
        exec_logical(instr, framestack, tempframe, lambda a, b: a and b)
    elif "OR" == instr.opcode:
        exec_logical(instr, framestack, tempframe, lambda a, b: a or b)
    elif "NOT" == instr.opcode:
        dest, symb = tuple(instr.args)
        symb = resolve_symbol(symb, framestack, tempframe)

        if symb.type == 'bool':
            dest = get_var(dest, framestack, tempframe)
            dest.type = 'bool'
            dest.value = not symb.value
        else:
            exit(RESULT_ERR_TYPE_COMPAT)

    elif "INT2CHAR" == instr.opcode:
        dest, symb = tuple(instr.args)
        symb = resolve_symbol(symb, framestack, tempframe)
        dest = get_var(dest, framestack, tempframe)
        exec_int2char(dest, symb)

    elif "STRI2INT" == instr.opcode:
        exec_binary(instr, exec_stri2int, framestack, tempframe)

    elif "DPRINT" == instr.opcode:
        symb = instr.args[0]
        symb = resolve_symbol(symb, framestack, tempframe)
        eprint(symb.value)

    elif "BREAK" == instr.opcode:
        # TODO maybe BREAK
        pass
    else:
        eprint("Unrecognized instruction: " + instr.opcode + "\n")
        # TODO error code?
        exit(667)
