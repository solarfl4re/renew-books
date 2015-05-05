#!/home/pi/renew/bin/python
# coding: utf8

# A script to renew our library books with the Anchorage Public Library and the UAA Consortium Library in Alaska.
# 
# TODO/FIXED list:
# DONE: schedule it to run with cron or st.
#   Or... let the script schedule itself?
#   Run 1-2 days before the next item is due, or in 6 days
#   - whichever is less. 6 days, because someone could check out a DVD...
# TODO: batch emails and send them all at once to save time.
# TODO: Add unit tests for email, possibly other things. Save a copy of the items dict
#         so we have everything we need.

from os import path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lxml import etree
from lxml.builder import E
from HTMLParser import HTMLParser

from datetime import datetime
from datetime import date

from time import sleep

import csv
import logging

# Imports for email
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

# This line helps if testing in IDLE.
# __file__ = 'C:/Python/library_renew_script/library_renew_books.py'

SCRIPT_DIR = path.dirname(__file__)
CSV_PATH = path.join(path.dirname(__file__), 'library_users.csv')
LOG_NAME = '{year}_LibraryRenewalScript.log'.format(year=date.today().year)
gmail_username = 'Your gmail address here'
gmail_password = 'Your gmail password here'

# Setup logging
logging.basicConfig(filename=LOG_NAME, format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

def get_users():
    '''Returns a list of dictionaries, one per user, of the format: [{name, email, username, password, library}, ...]
    CSV format: name, email, username, password, library'''
    
    users = []

    logging.info('Getting users from {csv_file}'.format(csv_file=CSV_PATH))

    with open(CSV_PATH) as csvfile:
      reader = csv.reader(csvfile, delimiter=',', quotechar='|')
      for line in reader:
          user = {}
          user['name'], user['email'], user['username'], user['password'], user['library'] = line[0], line[1], line[2], line[3], line[4]
          logging.debug('Got user: {0!s}'.format(user))
          users.append(user)
    return users

def get_phantomdriver():
    logging.info('Starting phantomjs Webdriver')
    driver = webdriver.phantomjs.webdriver.WebDriver(executable_path='/home/pi/bin/phantomjs')
    return driver

# From http://stackoverflow.com/a/925630 "I always used this function to strip 
# HTML tags, as it requires only the Python stdlib:"
class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def prepare_email_report(new_items_dict, user):
    """Using new_items_dict, builds an HTML-tree report to send,
    and returns HTML-as-string and stripped of tags HTML (text)."""

    html = (
        E.html(
            E.body(
                E.h3('Library Renewal script report', style='font-family: Helvetica, arial, sans-serif;'),
                E.p(E.strong('Account Name: '), user['name'], style='font: 13px Helvetica, arial, sans-serif;'),
                E.p('The library renewal script has renewed, or attempted to renew items for you. A report listing items that were renewed as well as those that could not be renewed is below.', style='font: 13px Helvetica, arial, sans-serif;'),
                E.p('If you notice any strange behaviour, or have questions about this script, please contact David Lane at ', E.a('david@armylane.com', href="mailto:david@armylane.com?Subject=Library%20Renewal%20Script", target="_top"), '.', style='font: 13px Helvetica, arial, sans-serif;'),
                E.h2('Renewed:', style='color: green; font-family: Helvetica, arial, sans-serif;'),
                E.table(
                    E.tr(
                        E.th('Title', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Author', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Renewals', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Due date', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Error', style='padding: 0.5rem; background-color: #ddd;')
                        ),
                    style='border-collapse: collapse; font-size: inherit; font: 13px Helvetica, arial, sans-serif; text-align: left;'),
                E.h2('Could not be renewed:', style='color: firebrick; font-family: Helvetica, arial, sans-serif;'),
                E.table(
                    E.tr(
                        E.th('Title', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Author', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Renewals', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Due date', style='padding: 0.5rem; background-color: #ddd;'),
                        E.th('Error', style='padding: 0.5rem; background-color: #ddd;')
                        ),
                    style='border-collapse: collapse; font-size: inherit; font: 13px Helvetica, arial, sans-serif; text-align: left;')
                )))
    
    renewed_table = html.findall('.//table')[0]
    not_renewed_table = html.findall('.//table')[1]

    for item in new_items_dict:
        error = new_items_dict[item].get('error')
        if error is None:
            error = ''

        item_tree = (E.tr(
            E.td(new_items_dict[item]['title'], style='padding: 0.5rem;'),
            E.td(new_items_dict[item]['author'], style='padding: 0.5rem;'),
            E.td('{0!s}'.format(new_items_dict[item]['renewals']), style='padding: 0.5rem;'),
            E.td(new_items_dict[item]['due_date'], style='padding: 0.5rem;'),
            E.td(error, style='padding: 0.5rem;'),
            ))
        if new_items_dict[item].get('renewed') is True:
            # Add an entry to the renewed table
            renewed_table.append(item_tree)
        elif new_items_dict[item].get('renewed') is False:
            # Add to the could-not-renew table
            not_renewed_table.append(item_tree)
        elif new_items_dict[item].get('error') is not None:
            # also add to the could-not-renew table
            not_renewed_table.append(item_tree)

    return etree.tostring(html), strip_tags(etree.tostring(html, pretty_print=True))

def create_message(html_report, text_report, email):
    logging.info('Creating the email message')

    # Create message container
    message = MIMEMultipart('alternative')
    message['Subject'] = 'Library Renewal Script Report'
    message['From'] = gmail_username
    message['To'] = email

    # Record the MIME types of both parts
    part1 = MIMEText(text_report.encode('utf-8'), 'plain')
    part2 = MIMEText(html_report.encode('utf-8'), 'html')

    # Attach the parts to message container
    message.attach(part1)
    message.attach(part2)

    return message

def send_email_report(message, name, email):
    logging.info('Sending a report to {name} at {email}'.format(name=name, email=email))

    # Send the message
    server = smtplib.SMTP(u'smtp.gmail.com', 587)
    try:
        server.ehlo()
        server.starttls()
        server.login(gmail_username, gmail_password)
    except smtplib.SMTPException as e:
        logging.critical('Error while connecting/logging in to gmail. Error:\n{}'.format(e))
        return False

    send_success = server.sendmail(gmail_username, email, message.as_string())
    if send_success != {} or '250':
        print('Failed to send mail. Error:\n{}'.format(send_success))
        server.quit()
        return False

    logging.info('Email sent to {}'.format(email))
    server.quit()
    print('Sent') 
    return True


def add_errors_to_items(page_source, items_dict):
    """Parses the page source and adds any error text to the item's dictionary in items_dict"""
    
    logging.info('Checking for errors after item renewal')

    root = etree.HTML(page_source)
    items = root.findall(".//tr[@class='checkoutsLine']")

    for item in items:
        # The ISBN is in the first span tag after 'authBreak'
        isbn = item.xpath(".//p[@class='authBreak']/span[1]")[0].text
        error = item.xpath(".//*[@class='checkoutsError']")
        if error:
            items_dict[isbn]['error'] = error[0].text
            logging.info('Error found for item {0}: {1}'.format(items_dict[isbn]['title'], items_dict[isbn]['error']))
            
def login(driver, username, password):
    driver.get('http://www.readytoreadak.org/apl/loginonly.html')
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'j_username')))
    except TimeoutException:
        print('Failed to find j_username after 10 seconds.')
        logging.critical('Failed to find login form while logging in to {user}, {password}. Login url: {login_url}'.format(user=username, password=password, login_url=login_url))
        return False
    print('Logging in as {}'.format(username))
    logging.info('Logging in as {}'.format(username))
    user_input = driver.find_element_by_id('j_username')
    user_input.send_keys(username)
    user_input = driver.find_element_by_id('j_password')
    user_input.send_keys(password)
    user_input.submit()

    try:
        WebDriverWait(driver, 10).until(EC.title_contains('My Account'))
    except TimeoutException as e:
        logging.warning('Couldn\'t log in with username: {0}, password: {1}'.format(username, password))
        return False
    sleep(0.3) # TODO: Remove, wait for whatever data we want to load instead
    return True
    
def open_checkout_tab(driver):
    logging.info('Getting account tabs (e.g. checkouts, holds)')
    link_bar = driver.find_element_by_id('accountTabs')
    checkouts_link = link_bar.find_element_by_partial_link_text('Checkouts')
    checkouts_link.click()

def get_isbn(auth_break):
    # If this item is a freak and has no isbn (unlikely),
    # accept the error from trying to run .text on a 'NoneType'
    # and set isbn to None so we know that it wasn't found
    try:
        isbn = auth_break.find(".//span").text
    except AttributeError as e:
        logging.warning('Couldn\'t get ISBN')
        isbn = None
    return isbn

def get_item_list(driver):
    ''' Parses checked out items and returns a list of dictionaries, one for each item
    Format: title, author, renewals, due date, can_renew(true or false)'''
    
    source = driver.page_source
    root = etree.HTML(source)
    items_dict = {}
    # Each checkoutsLine has one item; this gets them all
    items = root.findall(".//tr[@class='checkoutsLine']")

    # Use the driver to get a list of checkout lines so we can
    # get each items checkbox later
    checkout_lines = driver.find_elements_by_class_name('checkoutsLine')

    logging.info('--- Parsing checkoutsLine(s) to get title, author, isbn, and renewals')
    for i, item in enumerate(items):

        auth_break = item.find(".//p[@class='authBreak']")
        author = auth_break.text
        author = author.strip('\n\r')
        
        isbn = get_isbn(auth_break)
        try:
            # The item's checkbox has the item title, but it needs to be processed
            title = item.find(".//input[@type='checkbox']").attrib['title']
        except AttributeError as e:
            logging.warning('----+ Failed to get the title for item with ISBN: {0} and author: {1}'.format(isbn, author))
            logging.info('----+ Source for this chekoutsLine:\n{0}'.format(etree.tostring(item, pretty_print=True)))
            title = 'Unknown'

        # Before splitting, the title looks like 'Select Stonewall uprising [videorecording] .'
        # This gets rid of 'Select' and the final period
        title = title.split()[1:-1]

        # Join the split title together again
        title = " ".join(title)

        renewals = int(item.find(".//td[@class='checkoutsRenewCount']").text)
        due_date = item.find(".//td[@class='checkoutsDueDate']").text
        
        # Get the 'live' (e.g. from Chromedriver) checkoutLine for our item
        checkout_line = checkout_lines[i]

        try:
            checkbox = checkout_line.find_element_by_class_name('checkoutsCheckbox')
        except NoSuchElementException as e:
            logging.info('----+ No checkbox found for {0}'.format(title))
            checkbox = None

        # Make sure the checkbox is enabled - e.g. can we renew it?
        if checkbox is not None:
            can_renew = True
        else:
            can_renew = False
            checkbox = None

        logging.info('----+ Got {0}, due: {1}, renewable: {2}'.format(title, due_date, can_renew))

        items_dict[isbn] = {'title': title, 'author': author, 'isbn': isbn, 'renewals': renewals, 'due_date': due_date, 'can_renew': can_renew, 'checkbox': checkbox}
    
    logging.info('--- Finished preparing items_dict with {0} items, returning.'.format(len(items_dict.keys())))
        
    return items_dict

def renew(driver, items_dict, library):
    """
    Takes a list of all checked out items and the current library,
    and attempts to renew them. Returns the items renewed.
    """
    # For each item, check and see how days it is until it's due;
    # if it will be due in 2 days, add its ISBN to a list, which is
    # used to check the corresponding checkbox

    today = datetime.today()
    items_to_renew = []

    # Inside the loop, 'item' will be the ISBN of each item
    for item in items_dict:
        if items_dict[item]['can_renew'] is True:
            due = items_dict[item]['due_date']

            # Sometimes, there's a time as well, e.g. 3/6/14 23:59; this takes care of it
            due = due.split(' ')[0]

            due = datetime.strptime(due, r'%m/%d/%y')
            timedelta = due - today
            logging.info('Item {item_name} due on {due}, timedelta: {due} - {today} = {timedelta} day(s)'.format(item_name=items_dict[item]['title'], due=due, today=today, timedelta=timedelta.days))
            if timedelta.days <= 2:
                logging.info('Item {0} is due in 2 days or less; adding its ISBN to renew list'.format(items_dict[item]['title']))

                # Add the ISBNs of items that we want to renew
                # The item dict is indexed by ISBNs, so this works
                items_to_renew.append(items_dict[item]['isbn'])
            else:
                logging.info('Item {0} is due in {1} days; not going to renew'.format(items_dict[item]['title'], timedelta.days))


    if items_to_renew:
        # Check the checkbox for each item that will be due in # days
        logging.info('Checking {0} checkboxes for item renewal'.format(len(items_to_renew)))
        for isbn in items_to_renew:
            items_dict[isbn]['checkbox'].click()

        renew_button = driver.find_element_by_id('myCheckouts_checkoutslist_checkoutsRenewButton')

        logging.info('Renewing')
        renew_button.click()

        logging.info('Waiting for confirmation dialog to open')
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'myCheckouts_checkoutslist_checkoutsRenewButton')))

        # A confirm dialog with 'OK' and 'Cancel' comes up
        renew_confirm_button = driver.find_element_by_id('myCheckouts_checkoutslist_checkoutsDialogConfirm')
        renew_confirm_button.click()
        
        # TODO: replace with a wait for the checkoutlines - e.g. we know how many
        # of them there are, so count them and if they're all there, the page is loaded (enough)

        # wait for 2 seconds while the page reloads
        sleep(2)
    else:
        logging.info('No items to renew.')
    
    return items_to_renew

def logout(driver):
    # Logout, then wait until the page reloads - when the 'Log In' link reappears
    logging.info('Logging out.')
    logout_link = driver.find_element_by_link_text('Log Out')
    logout_link.click()
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.LINK_TEXT, "Log In")))
    except TimeoutException as e:
        logging.warning('Failed to find the Login link after 10 seconds.')
        return False
    sleep(0.5)
    return True
    
def renew_books():
    users = get_users()

    for user in users:
        driver = get_phantomdriver()
        renewed = None
        report = []

        logging.info('##### Going to log in as {0} #####'.format(user['name']))

        # Delete cookies before each user so we don't get weird errors
        driver.delete_all_cookies()

        login_success = login(driver, user['username'], user['password'])
        if login_success is False:
            logging.critical('Failed to log in as {0}. Username: {1} Password: {2}'.format(user['name'], user['username'], user['password']))
            continue
            
        logging.info('Logged in as {0}'.format(user['name']))
        
        open_checkout_tab(driver)

        # Wait for the items (checkoutLines) to be loaded; otherwise get_item_list finds nothing.
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'checkoutsLine')))
        except TimeoutException as e:
            logging.info('No checkoutsLine(s) found; {0} probably has no items checked out, or it took > 10 seconds to load'.format(user['name']))
        # Sleep for a second to give the silly site time to load
        sleep(1)

        items_dict = get_item_list(driver)
        # For testing REMOVE:
        try:
          date = datetime.today()
          filename = '{day}-{month}-{year}-items_dict.txt'.format(day=date.day, month=date.month, year=date.month)
          with open(filename, 'w') as f:
            f.write('{}'.format(items_dict))
        except error as e:
          logging.warning('Failed to write items_dict to file. Error:\n{}'.format(e))


        if items_dict:
            logging.info('{0} has {1} items checked out; calling renew() to renew as needed'.format(user['name'], len(items_dict.keys())))
            renewed = renew(driver, items_dict, user['library'])
        else:
            # If the user has no items checked out, skip to the next user
            logging.info('{0} has no items checked out; quitting driver and going to the next user'.format(user['name']))
            driver.quit()
            continue

        # Check for errors
        if renewed:
            logging.info('Items were renewed, getting new items_dict.')
            
            new_items_dict = get_item_list(driver)

            # add_errors_to_items modifies the item_list dictionary
            logging.info('Adding errors to items.')
            page_source = unicode(driver.page_source)
            add_errors_to_items(page_source, new_items_dict)
            
            # Compare due dates to find out which items were actually renewed
            logging.info('Comparing due dates to figure out what was renewed')
            for isbn in renewed:
                # If the due dates are the same before and after renewing, then the renewal failed
                if items_dict[isbn]['due_date'] == new_items_dict[isbn]['due_date']:
                    new_items_dict[isbn]['renewed'] = False

                # If they differ, it succeeded
                elif items_dict[isbn]['due_date'] != new_items_dict[isbn]['due_date']:
                    new_items_dict[isbn]['renewed'] = True
            
            # Format and prepare an email reporting renewed and not renewed items
            # TODO: use gmail api or st to send mail? - NO! What a failure. Why does it have to be
            # so stupid?
            html_report, text_report = prepare_email_report(new_items_dict, user)
            message = create_message(html_report, text_report, user['email'])
            send_success = send_email_report(message, user['name'], user['email'])

            if send_success is True:
                logging.info('Message sent to {user} successfully.'.format(user=user['email']))
            else:
                logging.warning('Failed to send message to {user}'.format(user=user['email']))
        else:
            logging.info('No items were renewed')
        logging.info('Quitting driver before next user.')
        driver.quit()

    logging.info('Done.')

if __name__ == '__main__':
    renew_books()
