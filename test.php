<?php
// TODO counters
define("RESULT_OK", 0);
define("RESULT_ERR_MISSING_ARG", 10);
define("RESULT_ERR_INVALID_ARGS", 10);

define("RESULT_ERR_OPENING_IN_FILE", 11);
define("RESULT_ERR_OPENING_OUT_FILE", 12);
define("RESULT_ERR_MISSING_FILE", 41);
define("RESULT_ERR_INTERNAL", 99);

// test output directory
const TEST_OUT_DIR = "test-out/";

$directory = ".";
$recursive = false;
$parser = "./parse.php";
$interpret = "./interpret.py";
$parseonly = false;
$intonly = false;
$jexampath = "/pub/courses/ipp/jexamxml/";
$clean = true;

/**
 * Prints string to STDERR
 */
function eprint(string $data, ?int $length = null): int|false {
    return fwrite(STDERR, $data, $length);
}

foreach($argv as $arg) {
    $a = explode("=", $arg, 2);

    switch($a[0]) {
        case "--help":
            //TODO help text
            exit(RESULT_OK);
        case "--directory":
            $directory = $a[1];
            break;
        case "--recursive":
            $recursive = true;
            break;
        case "--parse-script":
            $parser = $a[1];
            break;
        case "--int-script":
            $interpret = $a[1];
            break;
        case "--parse-only":
            $parseonly = true;
            break;
        case "--int-only":
            $intonly = true;
            break;
        case "--jexampath":
            $jexampath = $a[1];
            break;
        case "--noclean":
            $clean = false;
            break;
        case "test.php":
        case "./test.php":
            // nop
            break;
        default:
            eprint("Unrecognized argument: ".$arg."\n");
            exit(RESULT_ERR_INVALID_ARGS);
    }
}

function ensure_trailing_slash(&$path) {
    if (substr($path, -1) != "/") {
        $path .= "/";
    }
}

ensure_trailing_slash($directory);
if (!file_exists($directory)) {
    eprint("Specified --directory does not exist: $directory\n");
    exit(RESULT_ERR_MISSING_FILE);
}
if (!is_dir($directory)) {
    eprint("Specified --directory is not a directory: $directory\n");
    exit(RESULT_ERR_MISSING_FILE);
}

if ($parseonly && $intonly) {
    eprint("Both --int-only and --parse-only specified\n");
    exit(RESULT_ERR_INVALID_ARGS);
}

$test_parser = !$intonly;
$test_interpret = !$parseonly;

if ($parseonly || !$intonly) {
    if (!file_exists($parser)) {
        eprint("Parser does not exist: $parser!\n");
        exit(RESULT_ERR_MISSING_FILE);
    }
}

if ($parseonly || !$intonly) {
    if (!file_exists($interpret)) {
        eprint("Interpreter does not exist: $interpret!\n");
        exit(RESULT_ERR_MISSING_FILE);
    }
}

ensure_trailing_slash($jexampath);
if (!file_exists($jexampath."jexamxml.jar")) {
    eprint("jexamxml does not exist: $jexampath"."jexamxml.jar!\n");
    exit(RESULT_ERR_MISSING_FILE);
}

/*
 * @param test path/filename path and filename of the test files, path is relative to the tests directory, filename is without extension
 * @param outfile path/filename path and filename of the output files, path is relative to the tests directory, filename is without extension
 * @return false if test execution failed, true otherwise
 */
function exec_test($test, $outfile) {
    global $parser, $interpret, $test_parser, $test_interpret, $jexampath, $clean;

    eprint("Running test: $test\n");
    $command = "php8.1 $parser < $test.src > $outfile.xml";
    if (exec($command, result_code: $retcode) === false) {
        eprint("Failed executing shell command: $command $\n");
        return false;
    }

    // get expected return code from rc file
    $expect_rc = 0; // implicit if missing
    $test_rc = $test.".rc";
    if (file_exists($test_rc)) {
        $f = fopen($test_rc, 'r');
        if ($f === false) {
            eprint("Failed opening .rc file\n");
            exit(RESULT_ERR_OPENING_IN_FILE);
        }
        fscanf($f, "%d", $expect_rc); //TODO error checking
        fclose($f);
    } else {
        eprint("File $test_rc missing, generating it...\n");
        $f = fopen($test_rc, 'w');
        if ($f === false) {
            eprint("Failed creating .rc file\n");
            exit(RESULT_ERR_INTERNAL);
        }
        fwrite($f, '0'); // implicit value
        fclose($f);
    }

    $test_out = $test.".out";
    if (!file_exists($test_out)) {
        eprint("File $test_out missing, generating it...\n");
        fopen($test_out, 'c');
    }

    $test_in = $test.".in";
    if (!file_exists($test_in)) {
        eprint("File $test_in missing, generating it...\n");
        fopen($test_in, 'c');
    }

    if ($test_parser && !$test_interpret) {
        // parser only
        eprint("Expected: ".$expect_rc." got: ".$retcode."\n");

        if ($expect_rc == 0 && $retcode == 0) {
            eprint("Comparing outputs...\n");
            // compare parser xml output
            $expect_out = $test.".out";
            $command = "java -jar $jexampath"."jexamxml.jar $outfile.xml $expect_out";
            if (exec($command, result_code: $xml_rc) === false) {
                eprint("Failed executing jexamxml\n");
                return false;
            }
            generate_html($test, true, $xml_rc == 0);
        } else if ($expect_rc != $retcode) {
            generate_html($test, false, false);
        } else {
            generate_html($test, true, true);
        }
    }
    if ($test_interpret) {
        if ($test_parser)
            $test_src = $outfile.".xml";
        else
            $test_src = $test.".src";

        $command = "python3.8 $interpret --input=$test_in < $test_src > $outfile.out";
        if (exec($command, result_code: $int_rc) === false) {
            eprint("Failed executing interpreter\n");
            return false;
        }
        eprint("Expected: ".$expect_rc." got: ".$int_rc."\n");
        if ($expect_rc == 0 && $int_rc == 0) {
            // compare interpreter output
            eprint("Comparing diff outputs...\n");

            $command = "diff -Z $outfile.out $test.out";
            if (exec($command, result_code: $diff_rc) === false) {
                eprint("Failed executing diff, exit code: $diff_rc\n");
                return false;
            }
            generate_html($test, true, $diff_rc == 0);
        } elseif ($expect_rc == $int_rc) {
            generate_html($test, true, true);
        } else {
            generate_html($test, false, true);
        }

        if ($clean) {
            unlink($outfile.".out");
        }
    }
    if ($clean) {
        unlink($outfile.".xml");
    }
    return true;
}

function exec_tests_rec($dir, $path, $recursive)
{
    global $clean;
    eprint("In dir: $dir path: $path\n");
    $files = scandir($dir.$path);
    if (!$files) {
        eprint("Failed opening directory: ".$dir.$path."\n");
        exit(RESULT_ERR_OPENING_IN_FILE);
    }

    foreach ($files as $file) {

        if (is_dir($dir.$path.$file)) {
            // descend into dir
            if ($recursive && $file != "." && $file != "..") {
                exec_tests_rec($dir, $path.$file."/", $recursive);
                if ($clean) {
                    // remove test dir
                    rmdir(TEST_OUT_DIR.$path.$file);
                }
            }
        } elseif (is_file($dir.$path.$file)) {
            // exec the test
            $extension = pathinfo($file, PATHINFO_EXTENSION);
            $filename = pathinfo($file, PATHINFO_FILENAME);
            if ($extension == "src") {
                // prepare test output directory
                $out_dir = TEST_OUT_DIR.$path;
                if (!file_exists($out_dir))
                    mkdir($out_dir, recursive: true);

                $out_filename = $out_dir.$filename; // out file without extension
                $result = exec_test($dir.$path.$filename, $out_filename);
                if ($result === false)
                    eprint("WARNING: Failed executing test, continuing with next one...\n");
            }
        } else {
            eprint("File is not a regular file or directory: $file\n");
        }
    }
}

function html_begin() {
    $header =
    '<!DOCTYPE html>
        <html>
        <body>
            <table>
                <tr>
                    <th>Test</th>
                    <th>Result</th>
                    <th>Description</th>
                </tr>';
    print($header);
}

function html_end() {
    $footer = "</body>
               </html>";
    print($footer);
}

// TODO nicer html
function generate_html($testpath, $good_rc, $good_out) {
    if (!$good_rc) {
        $result = "Failed";
        $desc = "Bad exit code";
    } elseif (!$good_out) {
        $result = "Failed";
        $desc = "Bad output";
    } else {
        $result = "Passed";
        $desc = "";
    }

    $row = "<tr>
        <td>$testpath</td>
        <td>$result</td>
        <td>$desc</td>
    </tr>";
    print($row);
}

// create test output directory
if (!file_exists(TEST_OUT_DIR)) {
    mkdir(TEST_OUT_DIR, recursive: true);
}

html_begin();

eprint("Running in: $directory\n");
exec_tests_rec($directory, "", $recursive);

html_end();
?>
