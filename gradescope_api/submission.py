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


    def get_submission(self):
        '''Get the submission data for the current submission'''

        submission_resp = self.course.session.get(self.url)

        parsed_assignment_resp = BeautifulSoup(submission_resp.text, 'html.parser')

        #  <div data-react-class="AssignmentSubmissionViewer" data-react-props='{
        # select the data-react-props attribute as a json dict and parse it
        submission_data = parsed_assignment_resp.find('div', attrs={'data-react-class': 'AssignmentSubmissionViewer'})
        submission_data = submission_data.get('data-react-props')
        submission_data = json.loads(submission_data)



        with open('submission.html', 'w') as f:
            f.write(parsed_assignment_resp.prettify())










