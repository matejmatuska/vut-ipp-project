<?php
define("RESULT_OK", 0);
define("RESULT_ERR_MISSING_ARG", 10);
define("RESULT_ERR_INVALID_ARGS", 10);
define("RESULT_ERR_MISSING_FILE", 41);

const TEST_OUT_DIR = "test-out/";

$directory = ".";
$recursive = false;
$parser = "./parse.php";
$interpret = "./interpret.py";
$parseonly = false;
$intonly = false;
$jexampath = "/pub/courses/ipp/jexamxml/";
$noclean = false;

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
            $noclean = true;
            break;
        case "test.php":
            // nop
            break;
        default:
            echo "Unrecognized argument: ".$arg."\n";
            exit(RESULT_ERR_INVALID_ARGS);
    }
}

if (substr($directory, -1) != "/")
    // TODO for every arg
    $directory .= "/";

if (!file_exists($directory)) {
    echo "Specified --directory does not exist: $directory\n";
    exit(RESULT_ERR_MISSING_FILE);
}
if (!is_dir($directory)) {
    echo "Specified --directory is not a directory: $directory\n";
    exit(RESULT_ERR_MISSING_FILE);
}

if ($parseonly && $intonly) {
    echo "Both --int-only and --parse-only specified\n";
    exit(RESULT_ERR_INVALID_ARGS);
}

$test_parser = !$intonly;
$test_interpret = !$parseonly;

if ($parseonly || !$intonly) {
    if (!file_exists($parser)) {
        echo "Parser does not exist: $parser!\n";
        exit(RESULT_ERR_MISSING_FILE);
    }
}

if ($parseonly || !$intonly) {
    if (!file_exists($interpret)) {
        echo "Interpreter does not exist: $interpret!\n";
        exit(RESULT_ERR_MISSING_FILE);
    }
}

if (!file_exists($jexampath."jexamxml.jar")) {
    echo "jexamxml does not exist: $jexampath"."jexamxml.jar!\n";
    exit(RESULT_ERR_MISSING_FILE);
}


/*
 * @param test path/filename path and filename of the test files, path is relative to the tests directory, filename is without extension
 * @param outfile path/filename path and filename of the output files, path is relative to the tests directory, filename is without extension
 */
function exec_test($test, $outfile, $html) {
    global $parser, $interpret, $test_parser, $test_interpret;

    echo "Running test: $test\n";
    $command = "php $parser < $test.src > $outfile.xml";
    if (exec($command, result_code: $retcode) === false) {
        echo "Failed executing shell command: $command $\n";
        return false;
    }

    // get expected return code from rc file
    $expect_rc = 0;
    $test_rc = $test.".rc";
    if (file_exists($test_rc)) { //TODO if it doesnt we have to create it
        $f = fopen($test_rc, "r");
        if ($f === false) {
            //TODO failed opening rc file
            exit(667);
        }
        fscanf($f, "%d", $expect_rc); //TODO error checking
        fclose($f);
    } else {
        echo "File $test_rc missing, generating it...\n";
        fopen($test_rc, 'c');
    }

    $test_out = $test.".out";
    if (!file_exists($test_out)) {
        echo "File $test_out missing, generating it...\n";
        fopen($test_out, 'c');
    }

    $test_in = $test.".in";
    if (!file_exists($test_in)) {
        echo "File $test_in missing, generating it...\n";
        fopen($test_in, 'c');
    }

    if ($test_parser && !$test_interpret) {
        echo "Expected: ".$expect_rc." got: ".$retcode."\n";

        if ($expect_rc == 0 && $retcode == 0) {
            echo "Comparing outputs...\n";
            // compare parser xml output
            $expect_out = $test.".out";
            // TODO respect $jexampath setting
            $command = "java -jar jexamxml.jar $outfile.xml $expect_out -M options";
            if (exec($command, result_code: $xml_rc) === false) {
                echo "Failed executing jexamxml\n";
                return false;
            }
            generate_html($html, $test, true, $xml_rc == 0);
        } else if ($expect_rc != $retcode) {
            generate_html($html, $test, false, false);
        } else {
            generate_html($html, $test, true, true);
        }
    }
    if ($test_interpret) {
        if ($test_parser) 
            $test_src = $outfile.".xml";
        else
            $test_src = $test.".src";

        $command = "python3.8 $interpret --input=$test_in < $test_src > $outfile.out";
        if (exec($command, result_code: $int_rc) === false) {
            echo "Failed executing interpreter\n";
            return false;
        }
        echo "Expected: ".$expect_rc." got: ".$int_rc."\n";
        if ($expect_rc == 0 && $int_rc == 0) {
            // compare interpreter output
            echo "Comparing diff outputs...\n";

            $command = "diff -Z $outfile.out $test.out";

            if (exec($command, result_code: $diff_rc) === false) {
                echo "Failed executing diff, exit code: $diff_rc\n";
                return false;
            }
            generate_html($html, $test, true, $diff_rc == 0);
        } elseif ($expect_rc == $int_rc) {
            generate_html($html, $test, true, true);
        } else {
            generate_html($html, $test, false, true);
        }
    }
    return true;
}

function exec_tests_rec($dir, $path, $recursive, $html)
{
    echo "In dir: $dir path: $path\n";
    $files = scandir($dir.$path);
    if (!$files) {
        echo "Failed opening directory: ".$dir.$path."\n";
        exit(666); //TODO error code
    }

    foreach ($files as $file) {

        if (is_dir($dir.$path.$file)) {
            // descend into dir
            if ($recursive && $file != "." && $file != "..") {
                exec_tests_rec($dir, $path.$file."/", $recursive, $html);
            }
        } elseif (is_file($dir.$path.$file)) {
            // exec the test
            $extension = pathinfo($file, PATHINFO_EXTENSION);
            $filename = pathinfo($file, PATHINFO_FILENAME);
            if ($extension == "src") {
                // prepare outfile
                $out_dir = TEST_OUT_DIR.$path;
                if (!file_exists($out_dir))
                    mkdir($out_dir, recursive: true);

                $outfile = $out_dir.$filename; // out file without extension
                $result = exec_test($dir.$path.$filename, $outfile, $html);
                if ($result === false)
                    echo "Failed executing test, continuing with next one...\n";
            }
        } else {
            echo "File is not a regular file or directory: $file\n";
        }
    }
}

function html_begin() {
    $html = fopen("results.html", "w+");
    //TODO check for error

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
    fwrite($html, $header);
    return $html;
}

function html_end($html) {
    $footer = "</body>
    </html>";
    fwrite($html, $footer);
}

function generate_html($html, $testpath, $good_rc, $good_out) {
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
    fwrite($html, $row);
}

// create test output directory
if (!file_exists(TEST_OUT_DIR)) {
    mkdir(TEST_OUT_DIR, recursive: true);
}

$html = html_begin();

echo "running in: $directory\n";
exec_tests_rec($directory, "", $recursive, $html);

html_end($html);
?>
