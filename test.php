<?php
define("RESULT_OK", 0);
define("RESULT_ERR_MISSING_ARG", 10);
define("RESULT_ERR_INVALID_ARGS", 10);

define("RESULT_ERR_OPENING_IN_FILE", 11);
define("RESULT_ERR_OPENING_OUT_FILE", 12);
define("RESULT_ERR_MISSING_FILE", 41);
define("RESULT_ERR_INTERNAL", 99);

// test output directory
const TEST_OUT_DIR = "test-out/";

/**
 * Contains program arguments and their default value
 */
class Arguments {
    public $directory = ".";
    public $recursive = false;
    public $test_parser = true;
    public $test_interpret = true;
    public $parser = "./parse.php";
    public $interpret = "./interpret.py";
    public $jexampath = "/pub/courses/ipp/jexamxml/";
    public $clean = true;
}

/**
 * Prints string to STDERR
 */
function eprint(string $data, ?int $length = null): int|false {
    return fwrite(STDERR, $data, $length);
}

$parseonly = false;
$intonly = false;

$args = new Arguments;
foreach($argv as $arg) {
    $a = explode("=", $arg, 2);

    switch($a[0]) {
        case "--help":
            //TODO help text
            exit(RESULT_OK);
        case "--directory":
            $args->directory = $a[1];
            break;
        case "--recursive":
            $args->recursive = true;
            break;
        case "--parse-script":
            $args->parser = $a[1];
            break;
        case "--int-script":
            $args->interpret = $a[1];
            break;
        case "--parse-only":
            $parseonly = true;
            break;
        case "--int-only":
            $intonly = true;
            break;
        case "--jexampath":
            $args->jexampath = $a[1];
            break;
        case "--noclean":
            $args->clean = false;
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

/**
 * If missing, appends backslash to path
 */
function ensure_trailing_slash(&$path) {
    if (substr($path, -1) != "/") {
        $path .= "/";
    }
}

ensure_trailing_slash($args->directory);
if (!file_exists($args->directory)) {
    eprint("Specified --directory does not exist: $args->directory\n");
    exit(RESULT_ERR_MISSING_FILE);
}
if (!is_dir($args->directory)) {
    eprint("Specified --directory is not a directory: $args->directory\n");
    exit(RESULT_ERR_MISSING_FILE); // TODO nema to byt error opening in file?
}

if ($parseonly && $intonly) {
    eprint("Both --int-only and --parse-only specified\n");
    exit(RESULT_ERR_INVALID_ARGS);
}

$args->test_parser = !$intonly;
$args->test_interpret = !$parseonly;

if ($args->test_parser) {
    if (!file_exists($args->parser)) {
        eprint("Parser does not exist: $args->parser!\n");
        exit(RESULT_ERR_MISSING_FILE);
    }
}

if ($args->test_interpret) {
    if (!file_exists($args->interpret)) {
        eprint("Interpreter does not exist: $args->interpret!\n");
        exit(RESULT_ERR_MISSING_FILE);
    }
}

ensure_trailing_slash($args->jexampath);
if (!file_exists($args->jexampath."jexamxml.jar")) {
    eprint("jexamxml does not exist: $args->jexampath"."jexamxml.jar!\n");
    exit(RESULT_ERR_MISSING_FILE);
}

/*
 * @brief Executes one test case
 *
 * @param test path/filename path and filename of the test files,
 * path is relative to the tests directory, filename is without extension
 * @param outfile path/filename path and filename of the output files,
 * path is relative to the tests directory, filename is without extension
 * @return false if test execution failed, true otherwise
 */
function exec_test($test, $outfile, $args) {

    eprint("Running test: $test\n");

    $command = "php8.1 $args->parser < $test.src > $outfile.xml";
    if (exec($command, result_code: $retcode) === false) {
        eprint("Failed executing shell command: $command $\n");
        exit(RESULT_ERR_INTERNAL);
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
        fscanf($f, "%d", $expect_rc);
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
        fclose($test_out);
    }

    $test_in = $test.".in";
    if (!file_exists($test_in)) {
        eprint("File $test_in missing, generating it...\n");
        fopen($test_in, 'c');
        fclose($test_in);
    }

    $passed = false;
    if ($args->test_parser && !$args->test_interpret) {
        // parser only
        eprint("Expected: ".$expect_rc." got: ".$retcode."\n");

        if ($expect_rc == 0 && $retcode == 0) {
            eprint("Comparing outputs...\n");
            // compare parser xml output
            $expect_out = $test.".out";
            $command = "java -jar $args->jexampath"."jexamxml.jar $outfile.xml $expect_out";
            if (exec($command, result_code: $xml_rc) === false) {
                eprint("Failed executing jexamxml\n");
                exit(RESULT_ERR_INTERNAL);
            }
            $passed = $xml_rc == 0;
            generate_html($test, true, $xml_rc == 0);
        } else if ($expect_rc != $retcode) {
            generate_html($test, false, false);
        } else {
            $passed = true;
            generate_html($test, true, true);
        }
    }
    if ($args->test_interpret) {
        if ($args->test_parser)
            $test_src = $outfile.".xml";
        else
            $test_src = $test.".src"; // --int-only

        $command = "python3.8 $args->interpret --input=$test_in < $test_src > $outfile.out";
        if (exec($command, result_code: $int_rc) === false) {
            eprint("Failed executing interpreter\n");
            exit(RESULT_ERR_INTERNAL);
        }
        eprint("Expected: ".$expect_rc." got: ".$int_rc."\n");
        if ($expect_rc == 0 && $int_rc == 0) {
            // compare interpreter output
            eprint("Comparing diff outputs...\n");

            $command = "diff -Z $outfile.out $test.out";
            if (exec($command, result_code: $diff_rc) === false) {
                eprint("Failed executing diff, exit code: $diff_rc\n");
                exit(RESULT_ERR_INTERNAL);
            }
            $passed = $diff_rc == 0;
            generate_html($test, true, $diff_rc == 0);
        } else {
            $passed = $expect_rc == $int_rc;
            generate_html($test, $expect_rc == $int_rc, true);
        }

        if ($args->clean) {
            unlink($outfile.".out");
        }
    }
    if ($args->clean) {
        unlink($outfile.".xml");
    }
    return $passed;
}

/*
 * Contains stats about execution of tests
 */
class Stats {
    public $total = 0;
    public $passed = 0;
}

/*
 * @brief Execute tests in the given directory
 * and if running with --recursive it's subdirectories too
 */
function exec_tests_rec($dir, $path, $args, &$stats)
{
    eprint("In dir: $dir path: $path\n");

    $files = scandir($dir.$path);
    if (!$files) {
        eprint("Failed opening directory: ".$dir.$path."\n");
        exit(RESULT_ERR_OPENING_IN_FILE);
    }

    foreach ($files as $file) {

        if (is_dir($dir.$path.$file)) {
            // descend into dir
            if ($args->recursive && $file != "." && $file != "..") {
                exec_tests_rec($dir, $path.$file."/", $args, $stats);
            }
        } elseif (is_file($dir.$path.$file)) {
            // exec the test
            $filename = pathinfo($file, PATHINFO_FILENAME);
            $extension = pathinfo($file, PATHINFO_EXTENSION);
            if ($extension == "src") {
                // prepare test output directory
                $out_dir = TEST_OUT_DIR.$path;
                if (!file_exists($out_dir))
                    mkdir($out_dir, recursive: true);

                $out_filename = $out_dir.$filename; // out file without extension
                $result = exec_test($dir.$path.$filename, $out_filename, $args);
                if ($result) {
                    $stats->passed++;
                    eprint("PASSED\n");
                } else {
                    eprint("FAILED\n");
                }
                $stats->total++;
            }
        } else {
            eprint("File is not a regular file or directory: $file\n");
        }
    }
    if ($args->clean) {
        // current dir
        rmdir(TEST_OUT_DIR.$path);
    }
}

function html_begin() {
    $header =
    '<!DOCTYPE html>
    <html>
        <head>
        <style>
            table {
                float: left;
                border-collapse: collapse;
                border: 1px solid;
                margin: 10px;
            }

            td, th {
                padding-left: 8px;
                padding-right: 8px;
            }

            table.results {
                border-collapse: collapse;
                border: 1px solid;
            }
            table.results th {
                border: solid 1px;
            }
            table.results td {
                border-right: solid 1px;
                border-left: solid 1px;
            }
            table.results tr:nth-child(even) { background-color: #f2f2f2; }
            table.results td:nth-child(2) { text-align: center; }

            table.stats th {
                text-align: left;
                padding-left: 4px;
            }
            table.stats td:nth-child(2) { text-align: center; }
        </style>
        </head>
        <body>
            <table class="results" >
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

function generate_html($testpath, $good_rc, $good_out) {
    $row = "<tr>
        <td>$testpath</td>";

    if (!$good_rc) {
        $row = $row."<td style=\"background-color: #ffcdd0;\">Failed</td>";
        $desc = "Bad exit code";
    } elseif (!$good_out) {
        $row = $row."<td style=\"background-color: #ffcdd0;\">Failed</td>";
        $desc = "Bad output";
    } else {
        $row = $row."<td style=\"background-color: #c2ffd7;\">Passed</td>";
        $desc = "";
    }

    $row = $row."<td>$desc</td>
            </tr>";
    print($row);
}

// create test output directory
if (!file_exists(TEST_OUT_DIR)) {
    mkdir(TEST_OUT_DIR, recursive: true);
}

html_begin();

eprint("Running in: $args->directory\n");
$stats = new Stats;
exec_tests_rec($args->directory, "", $args, $stats);

eprint("Total: $stats->total\n");
eprint("Passed: $stats->passed\n");

$failed = $stats->total - $stats->passed;
$results = "
</table>
<table class=\"stats\">
    <tr>
    <th style=\"border: solid 1px; text-align: center;\" colspan=\"2\">Summary</th>
    </tr>
    <tr>
        <th>Total:</th>
        <td>$stats->total</td>
    </tr>
    <tr>
        <th>Passed:</th>
        <td>$stats->passed</td>
    </tr>
    <tr>
        <th>Failed:</th>
        <td>$failed</td>
    </tr>
</table>
</body>
</html>";
print($results);
?>
