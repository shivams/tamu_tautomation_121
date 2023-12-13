#!/usr/bin/env python
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import json


class GSSubmission():

    def __init__(self, subid, name, email, score, time, student_id, assignment):
        '''Create a submission object'''
        self.subid = str(subid)
        self.name = name
        self.email = email
        self.score = score
        self.time = time
        self.student_id = str(student_id)
        self.assignment = assignment
        self.course = assignment.course
        self.url = f"https://www.gradescope.com/courses/{self.course.cid}/assignments/{self.assignment.aid}/submissions/{self.subid}"










