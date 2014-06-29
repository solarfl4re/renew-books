# By Websten from forums
#
# Given your birthday and the current date, calculate your age in days.
# Account for leap days.
#
# Assume that the birthday and current date are correct dates (and no
# time travel).
#

def isLeapYear(year1, year2):
    # we make i = our bday and then count up until we hit the present year
    i = year1
    leap_days = 0
    start_year = year1
    end_year = year2-year1
    while i <= year2:
        if i/400:
            i = i + 1
            leap_days = leap_days + 1
        elif i/4:
            i = i + 1
            leap_days = leap_days + 1
        else: # not a leap year
            i = i + 1
    return leap_days

def daysInMonth(n):
    days_31 = '01 03 05 07 08 10 12' # the months with 31 days
    days_30 = '04 06 09 11'
    days_28 = '02'
    days = 0
    i = 0
    s = ''
    while i <= n:
        if n < 9:
            s = '0' + str(n)
            continue
        else:
            s = str(n)
            continue
        i = i + 1
        if days_28.find(s) >= 0:
            days = days + 28
        if days_30.find(s) >= 0:
            days = days + 30
        if days_31.find(s) >= 0:
            days = days + 31
        # if we have finished looping, return days
        else:
            return days


def daysBetweenDates(year1, month1, day1, year2, month2, day2):
    ##
    # Your code here.
    ##
    years = (year2 - year1) * 365
    # now need to get the # of days in the months, and subtract them from the total above
    #  because the above calculation assumes that on both ends of the year, it was a full year - that 'today' is the last day of december...
    days_in_month1 = daysInMonth(month1)
    days_in_month2 = daysInMonth(month2)
    print days_in_month1
    print days_in_month2

print 'Testing days in month(4): ' + str(daysInMonth(4)) # should be 120 days


# Test routine

def test():
    test_cases = [((2012,1,1,2012,2,28), 58),
                  ((2012,1,1,2012,3,1), 60),
                  ((2011,6,30,2012,6,30), 366),
                  ((2011,1,1,2012,8,8), 585 ),
                  ((1900,1,1,1999,12,31), 36523)]
    for (args, answer) in test_cases:
        result = daysBetweenDates(*args)
        if result != answer:
            print "Test with data:", args, "failed"
        else:
            print "Test case passed!"

test()
