from os import write
import sys;
import xml.etree.ElementTree as ET

RESULT_OK = 0
RESULT_ERR_XML_FORMAT = 31
RESULT_ERR_XML_STRUCTURE = 32

RESULT_ERR_SEMANTICS = 52 # var redefinition, undefined label
RESULT_ERR_TYPE_COMPAT = 53
RESULT_ERR_UNDEFINED_VAR = 54
RESULT_ERR_FRAME_NONEXISTENT = 55
RESULT_ERR_MISSING_VALUE = 56
RESULT_ERR_INVALID_OPERAND = 57
RESULT_ERR_STRING_MANIPULATION = 58

input = sys.stdin
source = sys.stdin

for arg in sys.argv:
    arg = arg.split("=", 2)
    if arg[0] == "interpret.py":
        pass # no-op
    elif arg[0] == "--help":
        # TODO print help
        exit(RESULT_OK);
    elif arg[0] == "--source":
        input = arg[1]
    elif arg[0] == "--input":
        source = arg[1]
    else:
        sys.stderr.write("Unrecognized argument: " + arg[0] + "\n");

tree = ET.parse(source)
root = tree.getroot()
if root.tag != "program":
    exit(RESULT_ERR_XML_FORMAT)

class TypedValue:

    def __init__(self, type, value):
        self.value = value
        self.type = type


class Instruction:

    def __init__(self, opcode, args): # order ma asi moc netrapi
        self.opcode = opcode
        self.args = args


def xml_parse_instruction(xmlElem):
    opcode = xmlElem.attrib['opcode']
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
        value == None

    return TypedValue(type, value)


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
        print('DEFVAR variable is already defined: ', arg.value)
        exit(RESULT_ERR_SEMANTICS)

    # TODO use typedvalue
    frame[name] = { 'type' : None, 'value' : None }


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
    ret =  TypedValue(var['type'], var['value'])
    if require_set and ret.value is None:
        exit(RESULT_ERR_MISSING_VALUE)
    return ret


def are_eq(sym1, sym2, framestack, tempframe):

    if sym1.value == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.value == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)
    #print(f"Comparing [{type1}, {val1}] and [{type2}, {val2}]")
    if sym1.type == sym2.type:
        return sym1.type == sym2.type
    else:
        exit(RESULT_ERR_TYPE_COMPAT)

def jump(labelmap, label):
    if label not in labelmap:
        exit(RESULT_ERR_SEMANTICS)

    return labelmap[label]


def write(instr):
    # TODO tie debilne unicode charactery
    arg = instr.args[0]
    if arg.type == 'var':
        arg = resolve_var(arg, framestack, tempframe)

    elif arg.type == "bool":
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


def exec_concat(instr, framestack, tempframe):
    dest = instr.args[0]
    sym1 = instr.args[1]
    sym2 = instr.args[2]

    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    if sym1.type == 'string' and sym2.type == 'string':
        get_var(dest, framestack, tempframe)['value'] = sym1.value + sym2.value
    else:
        exit(RESULT_ERR_TYPE_COMPAT)

def exec_artihmetic_impl(dest, sym1, sym2, operation):
    if sym1.type == 'int' and sym2.type == 'int':
        dest['type'] = 'int'
        result = operation(sym1.value, sym2.value)
        dest['value'] = result
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

    dest = get_var(dest, framestack, tempframe)
    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    if sym1.type == sym2.type:
        dest['type'] = 'bool'
        dest['value'] = operation(sym1.value, sym2.value)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


def exec_logical(instr, framestack, tempframe, operation):
    dest = instr.args[0]
    sym1 = instr.args[1]
    sym2 = instr.args[2]

    dest = get_var(dest, framestack, tempframe)
    if sym1.type == 'var':
        sym1 = resolve_var(sym1, framestack, tempframe)

    if sym2.type == 'var':
        sym2 = resolve_var(sym2, framestack, tempframe)

    if sym1.type == 'bool' and sym2.type == 'bool':
        dest['type'] = 'bool'
        dest['value'] = operation(sym1.value, sym2.value)
    else:
        exit(RESULT_ERR_TYPE_COMPAT)


instructions = list(root.iter("instruction"))
instructions.sort(key=lambda instr: int(instr.attrib['order']))

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
        labelmap[label] = pc

print(labelmap)


pc = 0
while pc < len(instructions):
    instr: Instruction = instructions[pc]
    print(pc, 'instruction: ' + instr.opcode)
    pc = pc + 1

    # print(pc - 1, instr.opcode)
    topframe = framestack[-1]

    if "DEFVAR" == instr.opcode:
        # works with any frame
        arg = instr.args[0]
        exec_defvar(arg, framestack, tempframe)

    elif "MOVE" == instr.opcode:
        # works with any frame
        dest = instr.args[0]
        src = instr.args[1]

        if (src.value == None):
            src.value = ''

        var = get_var(dest, framestack, tempframe)
        if var is None:
            exit(RESULT_ERR_UNDEFINED_VAR)

        if src.type == 'var':
            src = resolve_var(src, framestack, tempframe)

        var['type'] = src.type
        var['value'] = src.value

    elif "LABEL" == instr.opcode:
        pass

    elif "CALL" == instr.opcode:
        callstack.append(pc)
        pc = labelmap[instr.args[0].value]

    elif "RETURN" == instr.opcode:
        if not callstack:
            print('RETURN: Callstack is empty')
            exit(RESULT_ERR_MISSING_VALUE)
        pc = callstack.pop()

    elif "EXIT" == instr.opcode:
        exit_code = instr.args[0]
        
        if exit_code.type == 'var':
            var = get_var(exit_code, framestack, tempframe)
            exit_code.type = var['type']
            exit_code.value = var['value']

        if exit_code.value is None:
            exit(RESULT_ERR_MISSING_VALUE)

        if exit_code.type != 'int':
            exit(RESULT_ERR_TYPE_COMPAT)

        if exit_code.value < 0 or exit_code.value > 49:
            exit(RESULT_ERR_INVALID_OPERAND)

        print('EXITING with error code: ', exit_code.value)
        exit(exit_code.value)

    elif "CREATEFRAME" == instr.opcode:
        tempframe = {}

    elif "PUSHFRAME" == instr.opcode:
        if tempframe is None:
            exit(RESULT_ERR_FRAME_NONEXISTENT)

        framestack.append(tempframe)
        tempframe = None
    elif "POPFRAME" == instr.opcode:
        if len(framestack) == 1:
            print("POPFRAME: No available LF")
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

        if not are_eq(sym1, sym2, framestack, tempframe):
            pc = jump(labelmap, label)

    elif "WRITE" == instr.opcode:
        write(instr)

    elif "CONCAT" == instr.opcode:
        exec_concat(instr, framestack, tempframe)

    elif "STRLEN" == instr.opcode:
        dest = instr.args[0]
        symb = instr.args[1]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe)

        # TODO what if it isn't a string ??
        if symb.type != 'string':
            exit(RESULT_ERR_TYPE_COMPAT)

        length = len(symb.value)
        if dest.type == 'var':
            var = get_var(dest, framestack, tempframe)
            var['type'] = 'int'
            var['value'] = length
        else:
            # TODO nejaky error
            pass

    elif "TYPE" == instr.opcode:
        dest = instr.args[0]
        symb = instr.args[1]

        if symb.type == 'var':
            symb = resolve_var(symb, framestack, tempframe, require_set=False)
            if symb.value is None:
                # is symb is uninitialized variable type is empty string
                symb.type = ''

        dest = get_var(dest, framestack, tempframe)
        dest['type'] = 'string'
        dest['value'] = symb.type

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

        dest = get_var(dest, framestack, tempframe)
        if sym1.type == 'var':
            sym1 = resolve_var(sym1, framestack, tempframe)

        if sym2.type == 'var':
            sym2 = resolve_var(sym2, framestack, tempframe)

        if sym2.value == 0:
            exit(RESULT_ERR_INVALID_OPERAND)

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

        dest = get_var(dest, framestack, tempframe)
        if symb.type == 'bool':
            dest['type'] = 'bool'
            dest['value'] = not symb.value
        else:
            exit(RESULT_ERR_TYPE_COMPAT)
    else:
        sys.stderr.write("Unrecognized instruction: " + instr.opcode + "\n")
        exit(667)


print(framestack)
