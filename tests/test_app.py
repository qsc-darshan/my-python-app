import os
import subprocess
import sys
import time
import requests
from urllib.parse import urlparse
from tqdm import tqdm
import xml.etree.ElementTree as ET

# Mapping of test suites to categories
TEST_SUITES_DICT = {
    'controls': ['test_suite1', 'test_suite2'],
    'audio': ['test_suite3', 'test_suite8'],  # test_suite3 fails
    'android': ['test_suite4', 'test_suite5'],
    'plugin': ['test_suite6', 'test_suite9'],
    'video': ['test_suite7', 'test_suite10'],
}

# Constants
REPO_URL = "https://github.com/Darshan-qsc/Github-repo.git" 
GITHUB_TOKEN = ''
REPO_PATH = r"C:\Users\darshan.s\Documents\Automation_Run_for_Testing_QAT\repo"
XML_PATH = r"C:\Users\darshan.s\Documents\Automation_Run_for_Testing_QAT\config-file.xml"
JENKINS_URL = "http://urda:8080/job/SQA/job/QAT_Test_Automation_Source_Build/lastSuccessfulBuild/api/json"
LOG_FILE_PATH = r"C:\Users\darshan.s\AppData\Local\Temp\QSys Temp Files\QAT_CILogFile.txt"
QAT_FILE_PATH = r"C:\Users\darshan.s\Documents\Automation_Run_for_Testing_QAT\qat_start.bat"

# Add the token to the headers for authentication
HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}'
}

def get_test_suites(file_path, test_suites_dict):
    """
    Determine the test suites based on the file path.

    Args:
        file_path (str): Path of the file that was changed.
        test_suites_dict (dict): Mapping of categories to test suites.

    Returns:
        list: List of test suites relevant to the file path.
    """
    parts = file_path.split('/')
    file_changed = parts[0]
    results = []
    for key, suites in test_suites_dict.items():
        if file_changed.lower() in key.lower():
            results.append(suites)
    return results


def get_repo_info(repo_url):
    """
    Extract the owner and repository name from the GitHub URL.

    Args:
        repo_url (str): GitHub repository URL.

    Returns:
        tuple: Owner and repository name.
    """
    parsed_url = urlparse(repo_url)
    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise ValueError("Invalid GitHub URL format.")
    owner, repo = path_parts[0], path_parts[1].replace('.git', '')
    return owner, repo

def get_branches(owner, repo):
    """
    Fetch all branches of the repository.

    Args:
        owner (str): Repository owner.
        repo (str): Repository name.

    Returns:
        list: List of branch names.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/branches"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return [branch['name'] for branch in response.json()]

def get_commit_details(owner, repo, branch):
    """
    Fetch details of the latest commit in a branch.

    Args:
        owner (str): Repository owner.
        repo (str): Repository name.
        branch (str): Branch name.

    Returns:
        dict: Commit details including message, date, files URL, and author name.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    commit_data = response.json()
    return {
        'message': commit_data['commit']['message'],
        'date': commit_data['commit']['committer']['date'],  # Commit date is in 'committer' field
        'files_url': commit_data['url'],  # URL to get full commit info
        'author_name': commit_data['commit']['author']['name']  # Added to fetch the author's name
    }

def get_files_changed(commit_url):
    """
    Fetch the list of files changed in a commit.

    Args:
        commit_url (str): URL to fetch commit details.

    Returns:
        list: List of changed file paths.
    """
    response = requests.get(commit_url, headers=HEADERS)
    response.raise_for_status()
    commit_data = response.json()
    return [file['filename'] for file in commit_data.get('files', [])]

def find_latest_commit_with_files(repo_url):
    """
    Find the latest commit across all branches and fetch the files changed.

    Args:
        repo_url (str): GitHub repository URL.

    Returns:
        dict: Details of the latest commit including files changed.
    """
    owner, repo = get_repo_info(repo_url)
    branches = get_branches(owner, repo)

    latest_commit = None

    # Loop through each branch to find the latest commit
    for branch in branches:
        commit = get_commit_details(owner, repo, branch)
        
        # Update latest_commit if this commit is more recent
        if latest_commit is None or commit['date'] > latest_commit['date']:
            latest_commit = commit

    # Get files changed in the latest commit
    files_changed = get_files_changed(latest_commit['files_url'])
    latest_commit['files_changed'] = files_changed
    return latest_commit


def uncheck_all_test_suites(xml_path):
    """
    Uncheck all test suites in the XML configuration.

    Args:
        xml_path (str): Path to the XML configuration file.

    Returns:
        str: Success message.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for test_suite in root.findall(".//TestSuite"):
            for item in test_suite.iter():
                item.set('IsChecked', 'False')

        tree.write(xml_path)
        return "All TestSuites unchecked successfully."
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return "Failed to uncheck test suites."


def check_test_suite_items(xml_path, test_suite_name):
    """
    Check all items in a specific test suite.

    Args:
        xml_path (str): Path to the XML configuration file.
        test_suite_name (str): Name of the test suite to check.

    Returns:
        str: Success or error message.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        test_suite = root.find(f".//TestSuite[@Name='{test_suite_name}']")
        if test_suite is not None:
            for item in test_suite.iter():
                item.set('IsChecked', 'True')

            tree.write(xml_path)
            return f"{test_suite_name} checked successfully."
        else:
            return f"TestSuite '{test_suite_name}' not found."
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return f"Failed to check test suite '{test_suite_name}'."


def test_fetch_build_data(jenkins_url):
    """
    Fetch build data from Jenkins.

    Args:
        jenkins_url (str): Jenkins API URL.

    Returns:
        dict: JSON response containing build data, or None on failure.
    """
    try:
        response = requests.get(jenkins_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching build data: {e}")
        return None


def test_find_artifact(build_data, extension='.exe'):
    """
    Find an artifact with the specified extension in the build data.

    Args:
        build_data (dict): Jenkins build data.
        extension (str): File extension to search for.

    Returns:
        tuple: Artifact URL and file name, or (None, None) if not found.
    """
    for artifact in build_data.get('artifacts', []):
        if artifact['fileName'].endswith(extension):
            artifact_url = f"http://urda:8080/job/SQA/job/QAT_Test_Automation_Source_Build/lastSuccessfulBuild/artifact/{artifact['relativePath']}"
            return artifact_url, artifact['fileName']
    return None, None


def test_download_file(url, file_name):
    """
    Download a file from the specified URL with a progress bar.

    Args:
        url (str): URL of the file to download.
        file_name (str): Name to save the downloaded file as.

    Returns:
        str: Path to the downloaded file, or None on failure.
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        with open(file_name, "wb") as file, tqdm(
            desc=file_name,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)
        return file_name
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        return None


def install_exe(file_path):
    """
    Install the downloaded executable file.

    Args:
        file_path (str): Path to the executable file.

    Returns:
        None
    """
    try:
        subprocess.run([file_path, "/silent", "/v", "/qn"], check=True)
        print("----------------------------")
        print("Installation completed successfully.")
        print("----------------------------")
    except subprocess.CalledProcessError as e:
        print(f"Installation failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def run_scheduled_task(task_name, log_file_path):
    """
    Run a scheduled task and monitor its log file.

    Args:
        task_name (str): Name of the scheduled task to run.
        log_file_path (str): Path to the log file to monitor.

    Returns:
        str: Status of the task execution, or None on failure.
    """
    try:
        # Clear the log file before starting the task
        with open(log_file_path, 'w') as log_file:
            log_file.truncate(0)
    
        print(f"Log file cleared successfully.")

        subprocess.run(["schtasks", "/run", "/tn", task_name], check=True)
        print(f"Task '{task_name}' started successfully.")
        print("----------------------------")

        status = None
        with open(log_file_path, 'r') as log_file:
            while True:
                line = log_file.readline()
                if not line:
                    time.sleep(1)
                    continue
                print(line.strip())
                

                if "CI Execution status :" in line:
                    parts = line.split("::")
                    status = parts[1].split(":")[1].strip()
                
                if "QAT Ended................" in line:
                    print("QAT test run completed successfully.")
                    print("----------------------------")
                    break

        return status
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute task '{task_name}'. Error: {e}")
        return None
    except IOError as e:
        print(f"File operation failed. Error: {e}")
        return None
    
def test_run_bat_file(bat_file_path, log_file_path):
    """
    Run a .bat file and monitor its log file.

    Args:
        bat_file_path (str): Path to the .bat file to run.
        log_file_path (str): Path to the log file to monitor.

    Returns:
        str: Status of the task execution, or None on failure.
    """
    try:
        # Clear the log file before starting the task
        with open(log_file_path, 'w') as log_file:
            log_file.truncate(0)
    
        print(f"Log file cleared successfully.")

        subprocess.run([bat_file_path], check=True)
        print(f"Batch file '{bat_file_path}' started successfully.")
        print("----------------------------")

        status = None
        with open(log_file_path, 'r') as log_file:
            while True:
                line = log_file.readline()
                if not line:
                    time.sleep(1)
                    continue
                print(line.strip())
                
                if "CI Execution status :" in line:
                    parts = line.split("::")
                    status = parts[1].split(":")[1].strip()
                
                if "QAT Ended................" in line:
                    print("QAT test run completed successfully.")
                    print("----------------------------")
                    break

        return status
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute batch file '{bat_file_path}'. Error: {e}")
        return None
    except IOError as e:
        print(f"File operation failed. Error: {e}")
        return None


def test_check_status(status):
    """
    Check the status of the test run and exit the script if it failed.

    Args:
        status (str): Status of the test run.

    Returns:
        None
    """
    if status == "Pass":
        print("Test run passed.")
        print("----------------------------")
    else:
        print("Test run failed, failing the pipeline.")
        print("----------------------------")
        sys.exit(1)


def update_email_description(file_path, email_description_text):
    """
    Update the email description in the XML configuration.

    Args:
        file_path (str): Path to the XML configuration file.
        email_description_text (str): Text to set as the email description.

    Returns:
        None
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        for email_detail in root.findall('Emaildetails'):
            email_detail.set('EmailDescriptionCheck', 'True')
            email_detail.set('EmailDescriptionText', email_description_text)

        tree.write(file_path, encoding='utf-8', xml_declaration=True)
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")


if __name__ == "__main__":
    # Process the commit
    # latest = find_latest_commit_with_files(REPO_URL)
    # commit_message = latest['message']
    # files = latest['files_changed']
    # author_name = latest['author_name']
    # files_changed = files[0]
    # if not commit_message or not files_changed:
    #     sys.exit(1)

    # print("----------------------------")
    # print(f"Author Name: {author_name}")
    # print(f"Commit Message: {commit_message}")
    # print(f"File Changed: {files_changed}")
    # print("----------------------------")

    # Uncheck all test suites
    # print(uncheck_all_test_suites(XML_PATH))

    # # Check relevant test suites
    # test_suites = get_test_suites(files_changed, TEST_SUITES_DICT)
    # for suite in [item for sublist in test_suites for item in sublist]:
    #     print(check_test_suite_items(XML_PATH, suite))
    # print("----------------------------")

    # update_email_description(XML_PATH, commit_message)

    # Fetch build data from Jenkins
    build_data = test_fetch_build_data(JENKINS_URL)
    if build_data:
        artifact_url, artifact_name = test_find_artifact(build_data)
        if artifact_url and artifact_name:
            downloaded_file = test_download_file(artifact_url, artifact_name)
            if downloaded_file:
                print("----------------------------")
                print(f"File '{downloaded_file}' downloaded successfully!")
                print("----------------------------")
                # Install the .exe file
                # install_exe(downloaded_file)

                # Run the scheduled task
                # status = run_scheduled_task("RunQATAdmin", LOG_FILE_PATH)
                status = test_run_bat_file(QAT_FILE_PATH, LOG_FILE_PATH)
                test_check_status(status)
                
        else:
            print("No .exe file found in the latest build artifacts.")
    else:
        print("Failed to fetch build data.")
