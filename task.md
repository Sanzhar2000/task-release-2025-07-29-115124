# Test Assignment: GitHub Action SWE-bench Data Point Validator

**Assignment Type**: Infrastructure Development Test  
**Target Role**: Agent Infrastructure Developers  
**Time Estimate**: 6 hours

## Work Expectations

This assignment is designed to be completed as **your personal work** using modern LLM-powered coding tools such as Cursor, Roo Code, or Claude Code. We want to evaluate how effectively you can leverage AI tools to understand requirements, navigate codebases, and implement robust solutions.

## About SWE-bench

SWE-bench is a benchmark dataset for evaluating large language models on real-world software engineering tasks. It contains GitHub issues from popular Python repositories along with their corresponding pull requests that fix those issues.

**Repository**: [https://github.com/princeton-nlp/SWE-bench](https://github.com/princeton-nlp/SWE-bench)

Each data point includes:

- **Problem Statement**: Description of the bug or feature request
- **Test Cases**: Unit tests that verify the correct behavior
- **Expected Solution**: The actual code changes that resolve the issue
- **Repository Context**: Information about the codebase and environment

SWE-bench is used to test whether AI models can understand real software engineering problems and generate appropriate fixes.

## Task Overview

You are provided with a zip archive containing a working SWE-bench data downloader tool. Your task is to implement a validation system that ensures the quality and correctness of SWE-bench data points when they are committed to a repository.

## What You'll Receive

- Zip archive with:
  - Working SWE-bench data downloader implementation
  - **Two sample data points** in `data_points/` folder:
    - `astropy__astropy-11693.json` (valid data point)
    - `astropy__astropy-11693-fail.json` (invalid data point)
  - Project structure and configuration files
  - Technology stack setup (UV package manager, Python modules)

### Additional Data Points

You can download more data points for testing using the provided downloader:

```bash
# Download specific instance
scripts/download_swe_bench.sh --instance_id "django__django-10087"

# Download multiple instances from specific repository
scripts/download_swe_bench.sh --repo "django/django" --limit 5

# Download all instances (warning: large dataset)
scripts/download_swe_bench.sh --dataset "swe-bench/dev"
```

**Available data points include**:
- `astropy__astropy-*` - Astronomy library issues
- `django__django-*` - Web framework issues  
- `matplotlib__matplotlib-*` - Plotting library issues
- `scikit-learn__scikit-learn-*` - Machine learning library issues
- And many more Python repositories

Use additional data points to thoroughly test your validator implementation across different types of issues and repositories.

## Your Tasks

### 1. Document SWE-bench Docker Architecture

Create comprehensive documentation explaining how SWE-bench uses Docker for evaluation:
- **Docker Architecture Overview**: Document the 3-layer Docker system (Base → Environment → Instance images)
- **Image Building Process**: Explain when and how Docker images are built, including dependency installation
- **Test Execution Flow**: Detail how tests are executed within containers, including:
  - Patch application process
  - Test command execution with timeout handling
  - Output parsing and result extraction
  - **Concrete examples** showing actual execution scenarios
- **Integration Points**: How the validator integrates with this Docker infrastructure
- **When and where** data point requirements are installed in the Docker system

**Deliverable**: Create `swe-bench-docker-architecture.md` (expected size: 100-300 lines)

### 2. Implement SWE-bench Data Point Validator

Create a command-line validator script that:
- **Uses SWE-bench's official evaluation harness**:
  - Loads data points from JSON files in `data_points/` directory
  - Converts data points to SWE-bench prediction format using golden `patch` field
  - Runs `swebench.harness.run_evaluation` to test the patches
  - Validates that all tests in `FAIL_TO_PASS` and `PASS_TO_PASS` pass after patch application
- Provides detailed error messages for execution failures
- Handles timeouts and resource constraints appropriately

**Technical Requirements**:
- **Language**: Python with UV package manager for dependency management
- **Dependencies**: SWE-bench library, Docker for container execution  
- **Error Handling**: Handle both structural errors (malformed JSON, missing fields) and execution failures (Docker errors, test failures) with clear, actionable error messages
- **Timeouts**: Implement reasonable timeouts for evaluation runs (configurable per data point type)
- **Integration**: Work with existing project structure and maintain compatibility with UV package management

### 3. Create GitHub Action Workflow

Implement a GitHub Action (`.github/workflows/validate-datapoints.yml`) that:
- Triggers on pushes and pull requests affecting `data_points/**` files
- Detects only changed/new files in `data_points/` folder
- Runs validation on modified data points
- Reports validation results as status checks
- Provides detailed feedback on failures

**Technical Requirements**:
- **Triggers**: Only validate changed files in `data_points/**` (performance optimization - not existing files)
- **Performance**: Optimize for large datasets by processing only modified files
- **Error Handling**: Provide clear status check messages, include detailed logs for debugging failures
- **Automation**: Triggers automatically on pushes/PRs affecting `data_points/**` files
- **Status Reporting**: Reports validation results as status checks with detailed feedback

### 4. Repository Setup and Testing

1. **Push to Your Own Public Repository**: Create a new public repository with your implementation
2. **Create Two Test Pull Requests**:
   - **PR #1**: Add a valid data point that passes SWE-bench evaluation (all `FAIL_TO_PASS` and `PASS_TO_PASS` tests pass after patch application)
     - Example: `data_points/astropy__astropy-11693.json` is a valid data point
     - **Evidence Required**: Must show green status checks for validation
   - **PR #2**: Add an invalid data point that triggers validation failures. Examples of invalid data points:
     - Patch that fails to apply to the repository
     - Tests in `FAIL_TO_PASS` that still fail after applying the patch
     - Patch that breaks tests in `PASS_TO_PASS`
     - Data point that causes Docker evaluation errors
     - Example: `data_points/astropy__astropy-11693-fail.json` is an invalid data point (patch doesn't properly fix the issue)
     - **Evidence Required**: Must show red status checks with clear error explanations
   - **CI/CD Integration**: Both PRs must demonstrate proper CI/CD integration

## Deliverables

Your submission should include:

1. **SWE-bench Docker Architecture Documentation**:
   - Comprehensive specification document (`swe-bench-docker-architecture.md`)
   - Clear explanation of 3-layer Docker image system
   - Detailed test execution workflow documentation
   - Integration points with validation system

2. **Validator Implementation**:
   - Python validator script/module
   - CLI interface for running validation
   - Configuration file for validation rules

3. **GitHub Action**:
   - Workflow file (`.github/workflows/validate-datapoints.yml`)
   - Integration with the validator script
   - Proper changed-files detection

4. **General Documentation**:
   - README with setup and usage instructions
   - Examples of valid and invalid data points

5. **Testing Evidence**:
   - Link to your public repository with the implementation
   - Links to both test pull requests showing:
     - Successful validation (green status check)
     - Failed validation with clear error messages


## Getting Started

1. Extract the provided zip archive
2. Examine the existing data points and project structure
3. Understand the SWE-bench data format from sample files
4. Familiarize yourself with the SWE-bench evaluation harness and how it works ([Evaluation Guide](https://www.swebench.com/SWE-bench/guides/evaluation/), [Setup Guide](https://github.com/SWE-bench/SWE-bench?tab=readme-ov-file#-set-up))
5. **Study and Document SWE-bench Docker Architecture**: Analyze how SWE-bench uses Docker images, builds containers, and executes tests to create comprehensive documentation
6. Implement the validator based on the requirements above
7. Create the GitHub Action workflow
8. Test with the two required pull requests

## Submission Format

Please provide:
- **Public Repository URL** with your complete implementation
- **Brief explanation** of your approach and design decisions

Your repository should contain:
- **SWE-bench Docker Architecture Documentation** (`swe-bench-docker-architecture.md`) in the root directory
- **Working validator implementation** with CLI interface and GitHub Action
- **Two demonstration pull requests**:
  - PR #1: Valid data point that passes validation
  - PR #2: Invalid data point that fails validation with clear error messages

Good luck with your implementation! 