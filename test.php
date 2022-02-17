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
if ($parseonly || !$intonly) {
    if (file_exists($parser)) {
        echo "Parser does not exist: $parser!\n";
        exit(RESULT_ERR_MISSING_FILE);
    }
}

if ($parseonly || !$intonly) {
    if (file_exists($parser)) {
        echo "Interpreter does not exist: $interpret!\n";
        exit(RESULT_ERR_MISSING_FILE);
    }
}

if (!file_exists($jexampath."jexamxml.jar")) {
    echo "jexamxml does not exist: $jexampath"."jexamxml.jar!\n";
    exit(RESULT_ERR_MISSING_FILE);
}

function exec_test($test, $outfile, $html) {
    global $parser;

    echo "Running test: $test\n";
    if (!exec("php $parser < $test.src > $outfile", result_code: $retcode)) {
        //TODO failed to exec
    }

    // get expected return code from rc file
    $expect_rc = 0;
    $rc_filename = $test.".rc";
    if (file_exists($rc_filename)) { //TODO if it doesnt we have to create it
        $rc_file = fopen($rc_filename, "r");
        if ($rc_file === false) {
            //TODO failed opening rc file
            exit(667);
        }
        fscanf($rc_file, "%d", $expect_rc); //TODO error checking
        fclose($rc_file);
    } else {
        echo "rc file does not exist\n";
    }

    echo "Expected: ".$expect_rc." got: ".$retcode."\n";
    if ($expect_rc == 0 && $retcode == 0) {
        echo "Comparing outputs...\n";
        // compare outputs
        $expect_out = $test.".out";
        $command = "java -jar jexamxml.jar $outfile $expect_out -M options";
        if (!exec($command, result_code: $xml_rc)) {
            echo "Failed executing jexamxml\n";
        }

        generate_html($html, $test, true, $xml_rc == 0);
    } else if ($expect_rc != $retcode) {
        generate_html($html, $test, false, false);
    } else {
        generate_html($html, $test, true, true);
    }
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
            $extension = pathinfo($file,  PATHINFO_EXTENSION);
            $filename = pathinfo($file,  PATHINFO_FILENAME);
            if ($extension == "src") {
                // prepare outfile
                $out_dir = TEST_OUT_DIR.$path;
                if (!file_exists($out_dir))
                    mkdir($out_dir, recursive: true);

                $outfile = $out_dir.$filename.".xml";
                exec_test($dir.$path.$filename, $outfile, $html);
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
    $result = "Passed";
    $desc = "";
    if (!$good_rc) {
        $result = "Failed";
        if (!$good_out)
            $desc = "Bad output";
        else
            $desc = "Bad exit code";
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
