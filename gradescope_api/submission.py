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
        self.score = float(score)
        self.time = time
        self.student_id = str(student_id)
        self.assignment = assignment
        self.course = assignment.course
        self.url = f"https://www.gradescope.com/courses/{self.course.cid}/assignments/{self.assignment.aid}/submissions/{self.subid}"

        # Also activate the submission
        self.activate()

    def activate(self):
        '''Activate the submission'''
        #TODO: implement this
        # resp = self.course.session.get(self.url+"/activate")
        # print(resp.status_code)
        # This is not working
        pass













