<?php
/*
 * IPPcode22 parser
 *
 * Matej Matuška
 * xmatus36
 * 2022-03-16
 */
define("RESULT_OK", 0);
define("RESULT_ERR_MISSING_ARG", 10);
define("RESULT_ERR_INVALID_ARGS", 10);
define("RESULT_ERR_OPENING_IN_FILE", 11);
define("RESULT_ERR_OPENING_OUT_FILE", 12);

// exit codes reserved for parser
define("RESULT_ERR_INVALID_HEADER", 21);
define("RESULT_ERR_MISSING_HEADER", 21);
define("RESULT_ERR_INVALID_OPCODE", 22);
define("RESULT_ERR_MISSING_OPCODE", 22);
define("RESULT_ERR_LEX_OR_SYNTAX", 23);

define("RESULT_ERR_INTERNAL", 99);

ini_set('display_errors', 'stderr');

/**
 * Prints string to STDERR
 */
function eprint(string $data, ?int $length = null): int|false {
    return fwrite(STDERR, $data, $length);
}

if ($argc == 2 && strcmp("--help", $argv[1]) == 0) {
    eprint("Usage: parse|parse --help\n");
    exit(RESULT_OK);
} else if ($argc >= 2) {
    eprint("Unexpected arguments, see parse.php --help for usage\n");
    exit(RESULT_ERR_INVALID_ARGS);
}

/**
 * Returns string with trailing comment stripped
 * If line contains just comment returns empty string
 */
function strip_comment($line) {
    $index = strpos($line, "#");
    if ($index === false) {
        return $line;
    }
    return substr($line, 0, $index);
}

/**
 * Checks whether string is a valid variable identifier, including frame specification
 */
function check_var($var) {
    return preg_match("/^[GLT]F@[a-zA-Z_\-$&%*!?][\w\-$&%*!?]*$/", $var);
}

/**
 * Checks whether string is a valid label name
 */
function check_label($label) {
    return preg_match("/^[a-zA-Z_\-$&%*!?][\w\-$&%*!?]*$/", $label);
}

/**
 * Checks whether string is a valid type
 *
 * Valid types are "string", "int", "bool" and "nil"
 */
function check_type($type) {
    return $type == "string" || $type == "int" || $type == "bool" || $type == "nil";
}

/**
 * Checks whether string is a valid literal, including type definition
 */
function check_literal($lit) {
    return preg_match("/^int@[+-]?[0-9]+(_[0-9]+)*$/", $lit)            // decimal
        || preg_match("/^int@0[xX][0-9a-fA-F]+(_[0-9a-fA-F]+)*/", $lit) // hexadecimal
        || preg_match("/^int@0[oO]?[0-7]+(_[0-7]+)*/", $lit)             // octal
        || preg_match('/^string@(\\\\\d\d\d|[^\x00-\x20\x23\x5C])*$/u', $lit)
        || $lit == "bool@true" || $lit == "bool@false"
        || $lit == "nil@nil";
}

/**
 * Checks whether string is a valid symbol
 *
 * Symbol is either a variable or constant
 */
function check_symb($symb) {
    // const or var
    return (check_var($symb) || check_literal($symb));
}

/**
 * Converts reserved XML characters in string to their correct XML representation
 *
 * For example "<" is converted to "&lt"
 */
function xml_convert_special_chars($string) {
    $patterns = array("/&/", "/</", "/>/");
    $replacements = array("&amp;", "&lt;", "&gt;");
    return preg_replace($patterns, $replacements, $string);
}

/**
 * Generates a child XML element for a variable argument in the specified parent
 *
 * @param instr_xml parent XML element
 * @param index argument index
 * @param value variable name including frame specifier
 */
function xml_gen_var($instr_xml, $index, $value) {
    $value = xml_convert_special_chars($value);
    $arg1 = $instr_xml->addChild("arg".$index + 1, $value);
    $arg1->addAttribute("type", "var");
}

/**
 * Generates a child XML element for a label argument in the specified parent
 *
 * @param instr_xml parent XML element
 * @param index argument index
 * @param value label name
 */
function xml_gen_label($instr_xml, $index, $value) {
    $arg1 = $instr_xml->addChild("arg".$index + 1, $value);
    $arg1->addAttribute("type", "label");
}

/**
 * Generates a child XML element for a type argument in the specified parent
 *
 * @param instr_xml parent XML element
 * @param index argument index
 * @param value type
 */
function xml_gen_type($instr_xml, $index, $value) {
    $arg1 = $instr_xml->addChild("arg".$index + 1, $value);
    $arg1->addAttribute("type", "type");
}

/**
 * Generates a child XML element for a constant argument in the specified parent
 *
 * @param instr_xml parent XML element
 * @param index argument index
 * @param value constant value including type specifier
 */
function xml_gen_literal($instr_xml, $index, $value) {
    $type_and_val = explode('@', $value, 2);
    if ($type_and_val[1] == "string") {
        xml_convert_special_chars(type_and_val[1]);
    }
    $arg1 = $instr_xml->addChild("arg".$index + 1, $type_and_val[1]);
    $arg1->addAttribute("type", $type_and_val[0]);
}

/**
 * Generates a child XML element for a symbol argument in the specified parent
 *
 * @param instr_xml parent XML element
 * @param index argument index
 * @param value variable or constant
 */
function xml_gen_symb($instr_xml, $index, $value) {
    // const or var
    if (check_var($value)) {
        xml_gen_var($instr_xml, $index, $value);
    } elseif (check_literal($value)) {
        xml_gen_literal($instr_xml, $index, $value);
    } else {
        exit(RESULT_ERR_LEX_OR_SYNTAX);
    }
}

$xml = new SimpleXMLElement(
    '<?xml version="1.0" encoding="UTF-8"?><program></program>');
$xml->addAttribute('language', 'IPPcode22');

/**
 * Parses instruction and it's arguments or exits the script with appropriate error code
 *
 * @param opcode instruction opcode
 * @param args instructiom arguments
 * @param xml_parent parent XML element used for generating instruction and arg child elements
 * @param order instruction order
 */
function parse_instr($opcode, $args, $xml_parent, $order) {
    $instr = $xml_parent->addChild('instruction');
    $instr->addAttribute('order', $order);
    $instr->addAttribute('opcode', $opcode);

    switch ($opcode) {

        // var
        case "DEFVAR":
        case "POPS":
            if (count($args) != 1)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_var($args[0]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            xml_gen_var($instr, 0, $args[0]);
            break;

        // var symb
        case "NOT":
        case "MOVE":
        case "INT2CHAR":
        case "STRLEN":
        case "TYPE":
            if (count($args) != 2)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_var($args[0]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            if (check_symb($args[1]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            xml_gen_var($instr, 0, $args[0]);
            xml_gen_symb($instr, 1, $args[1]);
            break;

        // label
        case "CALL":
        case "LABEL":
        case "JUMP":
            if (count($args) != 1)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_label($args[0]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            xml_gen_label($instr, 0, $args[0]);
            break;

        // label sym1 sym2
        case "JUMPIFEQ":
        case "JUMPIFNEQ":
            if (count($args) != 3)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_label($args[0]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            if (check_symb($args[1]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            if (check_symb($args[2]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            xml_gen_label($instr, 0, $args[0]);
            xml_gen_symb($instr, 1, $args[1]);
            xml_gen_symb($instr, 2, $args[2]);
            break;

        // var type
        case "READ":
            if (count($args) != 2)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_var($args[0]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_type($args[1]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            xml_gen_var($instr, 0, $args[0]);
            xml_gen_type($instr, 1, $args[1]);
            break;

        // symb
        case "PUSHS":
        case "WRITE":
        case "EXIT":
        case "DPRINT":
            if (count($args) != 1)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_symb($args[0]) == 0) {
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            }

            xml_gen_symb($instr, 0, $args[0]);
            break;

        // no params
        case "CREATEFRAME":
        case "PUSHFRAME":
        case "POPFRAME":
        case "RETURN":
        case "BREAK":
            if (count($args) != 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            break;

        // var sym1 sym2
        case "ADD":
        case "SUB":
        case "MUL":
        case "IDIV":
        case "LT":
        case "GT":
        case "EQ":
        case "AND":
        case "OR":
        case "STRI2INT":
        case "GETCHAR":
        case "SETCHAR":
        case "CONCAT":
            if (count($args) != 3)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            if (check_var($args[0]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            if (check_symb($args[1]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);
            if (check_symb($args[2]) == 0)
                exit(RESULT_ERR_LEX_OR_SYNTAX);

            xml_gen_var($instr, 0, $args[0]);
            xml_gen_symb($instr, 1, $args[1]);
            xml_gen_symb($instr, 2, $args[2]);
            break;

        default:
            eprint("Unhandled or unrecognized instruction: ".$args[0]."\n");
            exit(RESULT_ERR_INVALID_OPCODE);
    }
}

$has_header = false;

$order = 1;
while ($line = fgets(STDIN)) {
    $line = strip_comment($line);
    $line = trim($line);

    if ($line == "")
        continue; // ignore empty lines (the ones containing just comment)

    if (!$has_header) {
        if (strcasecmp($line, ".IPPcode22") == 0) {
            $has_header = true;
            continue;
        } else {
            eprint("Missing file header\n");
            exit(RESULT_ERR_MISSING_HEADER);
        }
    }
    $split = preg_split("/\s+/", $line);
    $opcode = strtoupper(array_shift($split));

    parse_instr($opcode, $split, $xml, $order++);
}

// format the constructed XML and print it to stdout
$dom = new DOMDocument('1.0');
$dom->preserveWhiteSpace = false;
$dom->formatOutput = true;
$dom->loadXML($xml->asXML());
echo $dom->saveXML();
