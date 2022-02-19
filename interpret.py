import sys;
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


inputf = sys.stdin
sourcef = sys.stdin

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

class TypedValue:

    def __init__(self, type, value):
        self.value = value
        self.type = type

    def __str__(self):
        return f'TypedValue[type={self.type}, value={self.value}]'


class Instruction:

    def __init__(self, opcode, args):
        self.opcode = opcode
        self.args = args


def xml_parse_instruction(xmlElem):
    opcode = xmlElem.attrib['opcode']
    order = int(xmlElem.attrib['order'])
    if order < 0:
        eprint('Attribute "order" must be a positive number, was:', order)
        exit(RESULT_ERR_XML_FORMAT)

    args = []
    arg = xmlElem.find('arg1')
    if arg is not None:
        args.append(xml_parse_arg(arg))

        arg = xmlElem.find('arg2')
        if arg is not None:
            args.append(xml_parse_arg(arg))

            arg = xmlElem.find('arg3')
            if arg is not None:
                args.append(xml_parse_arg(arg))

    return Instruction(opcode, args)


def xml_parse_arg(arg):
    type = arg.attrib['type']
    value = arg.text

    if type == 'int':
        value = int(value)
    elif type == 'bool':
        if value == "true":
            value = True;
        elif value == "false":
            value = False;
        else:
            exit(666)
    elif type == 'string' and value is None:
        value = ''
    elif type == 'nil':
        value == 'nil'

    return TypedValue(type, value)


def jump(labelmap, label):
    if label not in labelmap:
        exit(RESULT_ERR_SEMANTICS)

    return labelmap[label]


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
        exit(RESULT_ERR_TYPE_COMPAT)

    if exit_code.value < 0 or exit_code.value > 49:
        exit(RESULT_ERR_INVALID_OPERAND)

    exit(exit_code.value)


def get_var(arg, framestack, tempframe):
    if arg.type != 'var':
        # TODO
        exit(500)

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

    if name not in frame:
        exit(RESULT_ERR_UNDEFINED_VAR)

    return frame[name]


# resolves symbol to variable
def resolve_var(symb, framestack, tempframe, require_set = True):
    var = get_var(symb, framestack, tempframe)
    if require_set and var.value is None:
        exit(RESULT_ERR_MISSING_VALUE)
    return var


def are_eq(sym1, sym2, framestack, tempframe):

    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    #print(sym1.type, sym1.value)
    #print(sym2.type, sym2.value)
    # TODO handle nil
    if sym1.type == sym2.type or sym1.value == 'nil' or sym2.value == 'nil':
        return sym1.value == sym2.value
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_read(dest, type):
    # TODO allow reading from file
    try:
        i = input()
    except EOFError:
        dest.type = 'nil'
        dest.value = 'nil'
        return

    if type.type == 'int':
        dest.type = 'int'
        # TODO catch exception when converting failed
        dest.value = int(i)
    elif type.type == 'string':
        dest.type = 'string'
        dest.value = i
    elif type.type == 'bool':
        dest.type = 'bool'
        dest.value = i.casefold() == 'true'
    else:
        # TODO
        pass


def exec_write(arg):
    # TODO tie debilne unicode charactery
    if arg.type == "bool":
        if arg.value == True:
            print("true", end='')
        else:
            print("false", end='')

    elif arg.type == "nil":
        print('', end='')

    elif arg.type == "string":
        s = arg.value.encode().decode('unicode-escape')
        #print(s, end='')
        print(s)
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
        dest.value = ord(char)
        dest.type = 'int'
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
    if (dest.type == 'string' and sym1.type == 'int'
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


def exec_artihmetic_impl(dest, sym1, sym2, operation):
    if sym1.type == 'int' and sym2.type == 'int':
        dest.type = 'int'
        result = operation(sym1.value, sym2.value)
        dest.value = result
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_artihmetic(instr, framestack, tempframe, operation):
    dest = instr.args[0]
    sym1 = instr.args[1]
    sym2 = instr.args[2]

    dest = get_var(dest, framestack, tempframe)
    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    exec_artihmetic_impl(dest, sym1, sym2, operation)


def exec_relational(instr, framestack, tempframe, operation):
    dest = instr.args[0]
    sym1 = instr.args[1]
    sym2 = instr.args[2]

    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    if sym1.type == sym2.type:
        dest = get_var(dest, framestack, tempframe)
        dest.type = 'bool'
        dest.value = operation(sym1.value, sym2.value)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_logical(instr, framestack, tempframe, operation):
    dest = instr.args[0]
    sym1 = instr.args[1]
    sym2 = instr.args[2]

    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    if sym1.type == 'bool' and sym2.type == 'bool':
        dest = get_var(dest, framestack, tempframe)
        dest.type = 'bool'
        dest.value = operation(sym1.value, sym2.value)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)

tree = ET.parse(sourcef)
root = tree.getroot()
if root.tag != "program":
    exit(RESULT_ERR_XML_FORMAT)

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
    # TODO dont allow negative order
    instructions[pc] = xml_parse_instruction(instr)
    pc = pc + 1

    if instr.attrib['opcode'] == 'LABEL':
        label = instr.find('arg1').text
        if label in labelmap:
            exit(RESULT_ERR_SEMANTICS)
        labelmap[label] = pc

# print("Label map:", labelmap)

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

        if src.type == 'var':
            src = resolve_var(src, framestack, tempframe)

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
        if exit_code.type == 'var':
            exit_code = resolve_var(exit_code, framestack, tempframe)

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
        label = instr.args[0].value
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        if are_eq(sym1, sym2, framestack, tempframe):
            pc = jump(labelmap, label)

    elif "JUMPIFNEQ" == instr.opcode:
        label = instr.args[0].value
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        # TODO should we check if label exists even when not jumping there ??

        if not are_eq(sym1, sym2, framestack, tempframe):
            pc = jump(labelmap, label)

    elif "READ" == instr.opcode:
        dest = instr.args[0]
        type = instr.args[1]

        dest = get_var(dest, framestack, tempframe)
        exec_read(dest, type)

    elif "WRITE" == instr.opcode:
        arg = instr.args[0]
        if arg.type == 'var':
            arg = resolve_var(arg, framestack, tempframe)
        exec_write(arg)

    elif "CONCAT" == instr.opcode:
        dest = instr.args[0]
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        if sym1.type == 'var':
            sym1 = resolve_var(sym1, framestack, tempframe)

        if sym2.type == 'var':
            sym2 = resolve_var(sym2, framestack, tempframe)

        dest = get_var(dest, framestack, tempframe)
        exec_concat(dest, sym1, sym2)

    elif "STRLEN" == instr.opcode:
        dest = instr.args[0]
        symb = instr.args[1]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe)

        if symb.type != 'string':
            exit(RESULT_ERR_TYPE_COMPAT)

        dest = get_var(dest, framestack, tempframe)
        dest.type = 'int'
        dest.value = len(symb.value)

    elif "GETCHAR" == instr.opcode:
        dest = instr.args[0]
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        if sym1.type == 'var':
            sym1 = resolve_var(sym1, framestack, tempframe)

        if sym2.type == 'var':
            sym2 = resolve_var(sym2, framestack, tempframe)

        dest = get_var(dest, framestack, tempframe)
        exec_getchar(dest, sym1, sym2)

    elif "SETCHAR" == instr.opcode:
        dest = instr.args[0]
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        if sym1.type == 'var':
            sym1 = resolve_var(sym1, framestack, tempframe)

        if sym2.type == 'var':
            sym2 = resolve_var(sym2, framestack, tempframe)

        dest = get_var(dest, framestack, tempframe)
        exec_setchar(dest, sym1, sym2)

    elif "TYPE" == instr.opcode:
        dest = instr.args[0]
        symb = instr.args[1]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe, require_set=False)
            if symb.value is None:
                # if symb is uninitialized variable type is empty string
                symb.type = ''

        dest = get_var(dest, framestack, tempframe)
        dest.type = 'string'
        dest.value = symb.type

    elif "PUSHS" == instr.opcode:
        symb = instr.args[0]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe)

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
        dest = instr.args[0]
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        if sym1.type == 'var':
            sym1 = resolve_var(sym1, framestack, tempframe)

        if sym2.type == 'var':
            sym2 = resolve_var(sym2, framestack, tempframe)

        if sym2.value == 0:
            exit(RESULT_ERR_INVALID_OPERAND)

        dest = get_var(dest, framestack, tempframe)
        exec_artihmetic_impl(dest, sym1, sym2, lambda a, b: a // b)

    elif "LT" == instr.opcode:
        exec_relational(instr, framestack, tempframe, lambda a, b: a < b)
    elif "GT" == instr.opcode:
        exec_relational(instr, framestack, tempframe, lambda a, b: a > b)
    elif "EQ" == instr.opcode:
        exec_relational(instr, framestack, tempframe, lambda a, b: a == b)
    elif "AND" == instr.opcode:
        exec_logical(instr, framestack, tempframe, lambda a, b: a and b)
    elif "OR" == instr.opcode:
        exec_logical(instr, framestack, tempframe, lambda a, b: a or b)
    elif "NOT" == instr.opcode:
        dest = instr.args[0]
        symb = instr.args[1]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe)

        if symb.type == 'bool':
            dest = get_var(dest, framestack, tempframe)
            dest.type = 'bool'
            dest.value = not symb.value
        else:
            exit(RESULT_ERR_TYPE_COMPAT)

    elif "INT2CHAR" == instr.opcode:
        dest = instr.args[0]
        symb = instr.args[1]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe)

        dest = get_var(dest, framestack, tempframe)
        exec_int2char(dest, symb)

    elif "STRI2INT" == instr.opcode:
        dest = instr.args[0]
        sym1 = instr.args[1]
        sym2 = instr.args[2]

        if sym1.type == 'var':
            sym1 = resolve_var(sym1, framestack, tempframe)

        if sym2.type == 'var':
            sym2 = resolve_var(sym2, framestack, tempframe)

        dest = get_var(dest, framestack, tempframe)
        exec_stri2int(dest, sym1, sym2)

    elif "DPRINT" == instr.opcode:
        symb = instr.args[0]
        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe)
        eprint(symb.value)

    elif "BREAK" == instr.opcode:
        # TODO maybe BREAK
        pass
    else:
        eprint("Unrecognized instruction: " + instr.opcode + "\n")
        # TODO error code?
        exit(667)
