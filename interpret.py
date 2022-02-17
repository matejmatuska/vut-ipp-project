from os import write
import sys;
import xml.etree.ElementTree as ET

RESULT_OK = 0
RESULT_ERR_XML_FORMAT = 31
RESULT_ERR_XML_STRUCTURE = 32

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
        sys.stderr.write("Unrecognized argument: " + arg[0]);

tree = ET.parse(source)
root = tree.getroot()
if root.tag != "program":
    exit(RESULT_ERR_XML_FORMAT)

instructions = list(root.iter("instruction"))
instructions.sort(key=lambda instr: instr.attrib['order'])

framestack = []
# add global frame
framestack.append({})

labelmap = {}

class Argument:

    def __init__(self, type, value):
        self.value = value
        self.type = type


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

    elif type == 'nil':
        value == None
        pass

    return Argument(type, value)


def jump_ifeq(sym1, sym2):
    type1 = sym1.type
    type2 = sym2.type

    val1 = sym1.value
    val2 = sym2.value

    if type1 == 'var':
        type1 = framestack[-1][sym1.value]['type']
        val1 = framestack[-1][sym1.value]['value']
    if type2 == 'var':
        type2 = framestack[-1][sym1.value]['type']
        val2 = framestack[-1][sym2.value]['value']

    if type1 == type2:
        if val1 == val2:
            return True
    else:
        return False

PC = 1 # program counter
for instr in instructions:
    print(PC)
    PC = PC + 1

    opcode = instr.attrib['opcode']

    if "DEFVAR" == opcode:
        arg = xml_parse_arg(instr.find('arg1'))
        framestack[-1][arg.value] = { 'type' : None, 'value' : None }
    elif "MOVE" == opcode:
        dest = xml_parse_arg(instr.find('arg1'))
        src = xml_parse_arg(instr.find('arg2'))

        if (src.value == None):
            src.value = ''

        framestack[-1][dest.value]['value'] = src.value
        framestack[-1][dest.value]['type'] = src.type
    elif "LABEL" == opcode:
        label = instr.find('arg1').text
        labelmap[label] = PC
    elif "JUMPIFEQ" == opcode:
        label = instr.find('arg1').text
        sym1 = xml_parse_arg(instr.find('arg2'))
        sym2 = xml_parse_arg(instr.find('arg3'))

        if jump_ifeq(sym1, sym2):
            PC = labelmap[label]
    elif "WRITE" == opcode:
        # TODO tie debilne unicode charactery
        arg = xml_parse_arg(instr.find('arg1'))
        if arg.type == 'var':
            val = framestack[-1][arg.value]['value']
            print(val, end='')
        elif arg.type == "bool":
            if arg.value == True:
                print("true", end='')
            else:
                print("false", end='')
        elif arg.type == "nil":
            print('', end='')
        else:
            print(arg.value, end='')
    else:
        pass
        #sys.stderr.write("Unrecognized instruction: " + opcode);


print(framestack)
print(labelmap)
