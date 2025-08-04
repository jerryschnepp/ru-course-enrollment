"""
Automate retrieval of Roosevelt University's Computer Science course enrollments.

This script uses Selenium to drive the RU Course Finder web‑application and
collect enrollment figures for all Computer Science and Information Technology
(subject code `CST`) courses offered in a given term.  The RU Course Finder
is an interactive web application that normally requires a user to select
various filters to see course information.  By automating those steps we
eliminate the repetitive point‑and‑click work and obtain a clean list of
courses and their enrollment numbers.

Prerequisites:
  * Python 3.7 or higher
  * Selenium (`pip install selenium`)
  * webdriver‑manager (`pip install webdriver-manager`)

The script uses Chrome in headless mode by default.  If you would like to
watch it run in a visible browser window, change the `headless` option to
False in the `get_driver()` function.

Term codes:
RU encodes academic terms with a six‑digit number where the first four
digits represent the academic year and the last two digits designate the
term (10 – Fall, 20 – Spring, 30 – Summer).  For example, Fall 2025 is
`202610`.  A few common examples are provided below:

  Term          Code
  ------------  -----
  Fall 2024     202510
  Spring 2025   202620
  Summer 2025   202630
  Fall 2025     202610

You can open the course finder manually and look at the URL or use the
`Select a Different Term` drop‑down to discover the code for a different
semester.

Usage:
    python cs_course_enrollment.py --term 202610

The script will print a table of courses (title, class code, enrolled/limit,
and wait list) to standard output.  You can also save the results as CSV
using the `--csv` option.

Author: ChatGPT (August 2025)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from typing import List

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class CourseInfo:
    """Simple container for the course information we care about."""

    title: str
    class_code: str
    enrolled: str
    wait_list: str


def get_driver(headless: bool = True) -> Chrome:
    """Initialise a Selenium Chrome WebDriver.

    Parameters
    ----------
    headless : bool
        Run the browser in headless mode.  Set to False if you want to
        watch the automation unfold in a real browser window.

    Returns
    -------
    Chrome
        An instance of Selenium's Chrome driver.
    """
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")  # use headless mode on modern Chrome
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    # Avoid detection where possible
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver_path = ChromeDriverManager().install()
    # Selenium 4 expects the driver path to be passed via a Service object.  Passing
    # the path as the first positional argument results in the
    # "got multiple values for argument 'options'" TypeError seen when using
    # newer versions of Selenium.  See:
    # https://selenium-python.readthedocs.io/api.html#selenium.webdriver.chrome.webdriver.WebDriver
    service = Service(driver_path)
    driver = Chrome(service=service, options=options)
    return driver


def collect_courses(term_code: str, headless: bool = True) -> List[CourseInfo]:
    """Collect computer science course enrollment information for a given term.

    This function drives a headless browser to select the CST subject and
    retrieve all course entries.  Each entry contains the course title,
    class code (e.g. CST 150‑01), the current enrollment/limit, and the
    wait list figures.  Results are returned as a list of `CourseInfo`.

    Parameters
    ----------
    term_code : str
        Roosevelt University term code (e.g. 202610 for Fall 2025).
    headless : bool
        Run the browser in headless mode; set to False to debug.

    Returns
    -------
    List[CourseInfo]
        A list of course information objects.
    """
    url = f"https://banner.roosevelt.edu/ssbprod/bwskzenr.P_CourseFinder?TERM={term_code}"
    driver = get_driver(headless=headless)
    try:
        driver.get(url)

        wait = WebDriverWait(driver, 20)

        # The subjects multi‑select list has the id "subjects"; wait for it.
        subjects_select = wait.until(EC.presence_of_element_located((By.ID, "subjects")))
        select = Select(subjects_select)

        # Select the computer science subject (code "CST").  We deselect any
        # previously selected option before selecting CST.
        select.deselect_all()
        select.select_by_value("CST")

        # Click the "Find Courses" button.  There is no unique id on the
        # button, so find it by its text.
        find_button = driver.find_element(By.XPATH, "//button[span[contains(@class,'ui-button-text') and contains(text(),'FIND COURSES')]]")
        find_button.click()

        # Wait for the results section to load.  We wait for at least one
        # courseResultBox entry to appear.
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.courseResultsBox .courseName")))

        # Scroll down to ensure all courses are rendered.  The results load
        # immediately, but some items may be outside the viewport; this scroll
        # ensures lazy‑loaded images or dynamic content has time to appear.
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        # Each course is contained within a DIV.courseResultsBox.  Inside each
        # there are several labelled fields.
        course_boxes = driver.find_elements(By.CSS_SELECTOR, "div.courseResultsBox")
        courses: List[CourseInfo] = []
        for box in course_boxes:
            try:
                title = box.find_element(By.CSS_SELECTOR, "div.courseName").text.strip()
                class_code = box.find_element(By.CSS_SELECTOR, "#classID .dataValue").text.strip()
                enrolled = box.find_element(By.CSS_SELECTOR, "#enrollID .dataValue").text.strip()
                wait_list = box.find_element(By.CSS_SELECTOR, "#waitID .dataValue").text.strip()
                courses.append(CourseInfo(title, class_code, enrolled, wait_list))
            except Exception:
                # Some boxes may be decorative or missing fields; skip them.
                continue

        return courses
    finally:
        driver.quit()


def print_courses(courses: List[CourseInfo]) -> None:
    """Print a simple table of courses to standard output."""
    if not courses:
        print("No courses were found.  Verify the term code and try again.")
        return
    # Determine column widths
    title_width = max(len("Title"), max(len(c.title) for c in courses))
    class_width = max(len("Class"), max(len(c.class_code) for c in courses))
    enrolled_width = max(len("Enrolled"), max(len(c.enrolled) for c in courses))
    wait_width = max(len("Wait List"), max(len(c.wait_list) for c in courses))
    # Note: there must be no spaces inside the format specifier braces.  Having
    # spaces (e.g. { 'Title':<{width} }) causes Python to interpret the space as
    # part of the format code, resulting in a ValueError.
    header = (
        f"{'Title':<{title_width}}  "
        f"{'Class':<{class_width}}  "
        f"{'Enrolled':<{enrolled_width}}  "
        f"{'Wait List':<{wait_width}}"
    )
    print(header)
    print("-" * len(header))
    for course in courses:
        row = (
            f"{course.title:<{title_width}}  "
            f"{course.class_code:<{class_width}}  "
            f"{course.enrolled:<{enrolled_width}}  "
            f"{course.wait_list:<{wait_width}}"
        )
        print(row)

    # Identify courses that either have low enrollment (<= 10 students enrolled)
    # or have one or more students on the wait list.  We'll parse the strings
    # like "9 / 25" and "0 / 46" to extract the current and limit values.  If
    # parsing fails we simply skip that course in this special section.
    def _parse_pair(pair: str) -> tuple[int, int]:
        try:
            current, limit = pair.split("/")
            return int(current.strip()), int(limit.strip())
        except Exception:
            return 0, 0

    flagged: List[CourseInfo] = []
    for c in courses:
        enrolled_current, _ = _parse_pair(c.enrolled)
        wait_current, _ = _parse_pair(c.wait_list)
        if enrolled_current <= 10 or wait_current > 0:
            flagged.append(c)

    if flagged:
        print("\nCourses of interest (≤ 10 enrolled or students on the wait list):")
        flagged_header = (
            f"{'Title':<{title_width}}  "
            f"{'Class':<{class_width}}  "
            f"{'Enrolled':<{enrolled_width}}  "
            f"{'Wait List':<{wait_width}}"
        )
        print(flagged_header)
        print("-" * len(flagged_header))
        for course in flagged:
            row = (
                f"{course.title:<{title_width}}  "
                f"{course.class_code:<{class_width}}  "
                f"{course.enrolled:<{enrolled_width}}  "
                f"{course.wait_list:<{wait_width}}"
            )
            print(row)


def save_csv(courses: List[CourseInfo], path: str) -> None:
    """Save the collected courses to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Class", "Enrolled", "Wait List"])
        for c in courses:
            writer.writerow([c.title, c.class_code, c.enrolled, c.wait_list])
    print(f"Saved {len(courses)} courses to {path}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieve RU computer science course enrollments.")
    parser.add_argument("--term", dest="term", required=True, help="Term code, e.g. 202610 for Fall 2025")
    parser.add_argument("--csv", dest="csv_path", help="Optional path to save results as CSV")
    parser.add_argument("--show-browser", action="store_true", help="Show the browser window instead of running headless")
    args = parser.parse_args(argv)

    courses = collect_courses(term_code=args.term, headless=not args.show_browser)
    print_courses(courses)
    if args.csv_path:
        save_csv(courses, args.csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())