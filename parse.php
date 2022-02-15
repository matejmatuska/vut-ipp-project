<?php
define("RESULT_OK", 0);
define("RESULT_ERR_MISSING_ARG", 10);
define("RESULT_ERR_INVALID_ARGS", 10);
define("RESULT_ERR_OPENING_IN_FILE", 11);
define("RESULT_ERR_OPENING_OUT_FILE", 12);

// 20-69 navratove kody chyb specifickych pro jednotlive skripty
define("RESULT_ERR_INVALID_HEADER", 21);
define("RESULT_ERR_MISSING_HEADER", 21);
define("RESULT_ERR_INVALID_OPCODE", 22);
define("RESULT_ERR_MISSING_OPCODE", 22);
define("RESULT_ERR_OTHER_LEX", 23);
define("RESULT_ERR_OTHER_SYNTAX", 23);

define("RESULT_ERR_INTERNAL", 99);

function strip_comment($line) {
    $index = strpos($line, "#");
    if ($index === false) {
        return $line;
    }
    return substr($line, 0, $index);
}

if ($argc == 2 && strcmp("--help", $argv[1]) == 0) {
    echo "Usage: parse|parse --help\n";
    exit(RESULT_OK);
}
else if ($argc >= 2) {
    //TODO print error msg to stderr
    exit(RESULT_ERR_INVALID_ARGS);
}

function check_var($var) {
    return preg_match("/^[GLT]F@[a-zA-Z_\-$&%*!?][\w\-$&%*!?]*$/", $var);
}

function check_label($label) {
    return preg_match("/^[a-zA-Z_\-$&%*!?][\w\-$&%*!?]*$/", $label);
}

function check_const($const) {
    return preg_match("/^int@\-?[1-9]\d*$/", $const)
        || preg_match("/^string@[\x{000}-\x{3E7}]*/u", $const)
        || $const == "bool@true" || $const == "bool@false"
        || $const == "nil@nil";
}

function check_symb($symb) {
    // const or var
    return (check_var($symb) !== 0) || check_const($symb);
}

function xml_gen_var($instr_xml, $index, $value) {
    $arg1 = $instr_xml->addChild("arg".$index, $value);
    $arg1->addAttribute("type", "var");
}

function xml_gen_label($instr_xml, $index, $value) {
    $arg1 = $instr_xml->addChild("arg".$index, $value);
    $arg1->addAttribute("type", "label");
}

function xml_gen_const($instr_xml, $index, $value) {
    $type_and_val = explode('@', $value);
    $arg1 = $instr_xml->addChild("arg".$index, $type_and_val[1]);
    $arg1->addAttribute("type", $type_and_val[0]);
}

function xml_gen_symb($instr_xml, $index, $value) {
    // const or var
    if (check_var($value)) {
        xml_gen_var($instr_xml, $index, $value);
    } elseif (check_const($value)) {
        xml_gen_const($instr_xml, $index, $value);
    } else {
        exit(RESULT_ERR_INVALID_ARGS);
    }
}

$has_header = false;

$xml = new SimpleXMLElement(
    '<?xml version="1.0" encoding="UTF-8"?><program></program>');
$xml->addAttribute('language', 'IPPcode22');

$order = 1;
while ($line = fgets(STDIN)) {
    $line = strip_comment($line);
    if ($line == "")
        continue; // ignore empty lines (the ones containing just comment)

    $line = trim($line);

    if (!$has_header) {
        if ($line == ".IPPcode22") {
            $has_header = true;
            continue;
        } else {
            exit(RESULT_ERR_MISSING_HEADER);
        }
    }

    //echo ($line)."\n";
    $split = preg_split("/\s+/", $line);
    $opcode = strtoupper($split[0]);

    $instr = $xml->addChild('instruction');
    $instr->addAttribute('order', $order++);
    $instr->addAttribute('opcode', $opcode);
    switch ($opcode) {

        // var
        case "DEFVAR":
        case "POPS":
            if (count($split) != 2)
                exit(RESULT_ERR_OTHER_SYNTAX);

            if (check_var($split[1]) === 0)
                exit(RESULT_ERR_OTHER_SYNTAX);

            xml_gen_var($instr, 1, $split[1]);
            break;

        // var symb
        case "MOVE":
        case "INT2CHAR":
        case "STRLEN":
        case "TYPE":
            if (count($split) != 3)
                exit(RESULT_ERR_MISSING_ARG);

            check_var($split[1]);
            check_symb($split[2]);
            xml_gen_var($instr, 1, $split[1]);
            xml_gen_symb($instr, 2, $split[2]);
            break;

        // label
        case "CALL":
        case "LABEL":
        case "JUMP":
            if (count($split) != 2)
                exit(RESULT_ERR_MISSING_ARG);

            check_label($split[1]);
            xml_gen_label($instr, 1, $split[1]);
            break;

        // label sym1 sym2
        case "JUMPIFEQ":
        case "JUMPIFNEQ":
            if (count($split) != 4)
                exit(RESULT_ERR_MISSING_ARG);

            check_label($split[1]);
            check_symb($split[2]);
            check_symb($split[3]);
            xml_gen_label($instr, 1, $split[1]);
            xml_gen_symb($instr, 2, $split[2]);
            xml_gen_symb($instr, 3, $split[3]);
            break;

        // var type
        case "READ":
            if (count($split) != 3)
                exit(RESULT_ERR_MISSING_ARG);

            check_var($split[1]);
            //TODO type
            break;

        // symb
        case "PUSHS":
        case "WRITE":
        case "EXIT":
        case "DPRINT":
            if (count($split) != 2)
                exit(RESULT_ERR_MISSING_ARG);
            check_symb($split[1]);
            xml_gen_symb($instr, 1, $split[1]);
            break;

        // no params
        case "CREATEFRAME":
        case "PUSHFRAME":
        case "POPFRAME":
        case "RETURN":
        case "BREAK":
            if (count($split) != 1)
                exit(RESULT_ERR_MISSING_ARG);
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
        case "NOT":

        case "STRI2INT":
        case "GETCHAR":
        case "SETCHAR":
        case "CONCAT":
            if (count($split) != 4)
                exit(RESULT_ERR_OTHER_SYNTAX);

            check_var($split[1]);
            check_symb($split[2]);
            check_symb($split[3]);

            xml_gen_var($instr, 1, $split[1]);
            xml_gen_symb($instr, 2, $split[2]);
            xml_gen_symb($instr, 3, $split[3]);
            break;

        default:
            echo "Unhandled or unrecognized instruction: ".$split[0]."\n";
            exit(RESULT_ERR_INVALID_OPCODE);
    }
}

$dom = new DOMDocument('1.0');
$dom->preserveWhiteSpace = false;
$dom->formatOutput = true;
$dom->loadXML($xml->asXML());
echo $dom->saveXML();
