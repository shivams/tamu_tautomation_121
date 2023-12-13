import requests
from bs4 import BeautifulSoup
try:
   from question import GSQuestion
   from submission import GSSubmission
except ModuleNotFoundError:
   from .question import GSQuestion
   from .submission import GSSubmission
import json
import os
import zipfile
import tempfile
from datetime import datetime
from time import sleep

SUBMISSIONS_PATH = 'submissions'

class GSAssignment():

    def __init__(self, name, aid, points, percent_graded, complete, regrades_on, course, due_date):
        '''Create a assignment object'''
        self.name = name
        self.aid = aid
        self.points = points
        self.percent_graded = percent_graded
        self.complete = complete
        self.regrades_on = regrades_on
        self.course = course
        self.due_date = due_date
        self.questions = []
        self.submissions = []


    def post_submission(self, fname, student_id):
        '''
        Upload Code files for a submission.
        fname: The name of the zip file which contains the files to upload
        '''

        # First, get the authenticity_token
        submission_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                    '/assignments/'+self.aid+'/submissions/new?owner_id='+student_id)
        parsed_assignment_resp = BeautifulSoup(submission_resp.text, 'html.parser')
        authenticity_token = parsed_assignment_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        # Now, post the submission
        params = {
            "submission[owner_id]": student_id,
            "utf8": "✓",
            "authenticity_token": authenticity_token,
            "submission[method]": "upload",
            "null": "",
            "submission[leaderboard_name]": ""
        }

        headers = {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the zip file
            with zipfile.ZipFile(fname, 'r') as thezip:
                thezip.extractall(temp_dir)

            submission_files = []
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                submission_files.append(('submission[files][]', (filename, open(file_path, 'rb'), 'application/octet-stream')))


            submission_resp = self.course.session.post('https://www.gradescope.com/courses/'+self.course.cid+
                                                        '/assignments/'+self.aid+'/submissions',
                                                        data = params,
                                                        files = submission_files,
                                                        headers=headers)

        # parse submission response json
        #  '{"success":true,"url":"/courses/569119/assignments/3394470/submissions/215229408"}'
        submission_json = json.loads(submission_resp.text)
        if submission_resp.status_code != requests.codes.ok or not submission_json['success']:
            return False

        # Else: proceed to check the status of the submission and return the submission when it's graded
        submission_url = 'https://www.gradescope.com'+submission_json['url']+'.json?content=react'
        while True:
            try:
                submission_resp = self.course.session.get(submission_url)
                submission_json = json.loads(submission_resp.text)
                #  import ipdb; ipdb.set_trace()
                score = submission_json['assignment_submission']['score']
                time = datetime.fromisoformat(submission_json['assignment_submission']['created_at'])
                submission_id = submission_json['assignment_submission']['id']
                name = submission_json['course_members'][0]['name']
                email = submission_json['course_members'][0]['email']
                if score:
                    break
            except:
                print("Waiting for the submission to be graded...")
                sleep(5) # wait 5 seconds before trying again

        print(f"Submission successfully posted for {name} with score {score}")
        return GSSubmission(subid=submission_id, name=name, email=email, score=score,
                            time=time, student_id=student_id, assignment=self)



    def get_submission(self, email, maxdate=None):
        '''
        email: The email of the student whose submission we want to get.
        maxdate (optional): datetime object. If provided, only submissions on or before this date will be considered.
        Returns a submission object for the given email.
        '''
        submission_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                  '/assignments/'+self.aid+'/review_grades')
        parsed_submission_resp = BeautifulSoup(submission_resp.text, 'html.parser')

        table = parsed_submission_resp.find('table', attrs={'class':'table js-reviewGradesTable'})
        tbody = table.find('tbody')
        for row in tbody.find_all('tr'):
            name = row.find_all('td')[0].text
            if not row.find_all('td')[0].find_all('a'):
                # if there is no link, there is no submission
                continue
            if email == row.find_all('td')[2].text:
                submission_id = row.find_all('td')[0].find_all('a')[0].get('href').split('/')[-1]
                submission = self.get_highest_score_submission(submission_id, maxdate)
                if not submission:
                    return None
                score = submission['score']
                time = datetime.fromisoformat(submission['created_at'])
                submission_id = submission['id']
                student_id = submission['owners'][0]['id']
                return GSSubmission(subid=submission_id, name=name, email=email, score=score,
                                    time=time, student_id=student_id, assignment=self)

        return None


    def get_submissions(self, download=False):
        '''
        Get the list of submissions for this assignment.
        '''
        #  submission_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                  #  '/assignments/'+self.aid+'/submissions')
        #  parsed_submission_resp = BeautifulSoup(submission_resp.text, 'html.parser')
        #  with open('submissions.html', 'w') as f:
            #  f.write(str(parsed_submission_resp))

        submission_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                  '/assignments/'+self.aid+'/review_grades')
        parsed_submission_resp = BeautifulSoup(submission_resp.text, 'html.parser')
        with open('review_grades.html', 'w') as f:
            f.write(str(parsed_submission_resp))


        table = parsed_submission_resp.find('table', attrs={'class':'table js-reviewGradesTable'})
        tbody = table.find('tbody')
        for row in tbody.find_all('tr'):
            name = row.find_all('td')[0].text
            if not row.find_all('td')[0].find_all('a'):
                # if there is no link, there is no submission
                print(f"No submission for {name}")
                continue
            submission_id = row.find_all('td')[0].find_all('a')[0].get('href').split('/')[-1]
            email = row.find_all('td')[2].text

            submission = self.get_highest_score_submission(submission_id)

            score = submission['score']
            time = datetime.fromisoformat(submission['created_at'])
            submission_id = submission['id']
            student_id = submission['owners'][0]['id']
            print(f"Adding submission {submission_id} for {name} with score {score} at {time}")

            #  (subid, name, email, score, time, student_id, assignment):
            self.submissions.append(GSSubmission(subid=submission_id, name=name, email=email, score=score,
                                                 time=time, student_id=student_id, assignment=self))


            if download:
                submission_zip_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                                '/assignments/'+self.aid+'/submissions/'+submission_id+'.zip')
                # if submissions path does not exist, create it
                if not os.path.exists(SUBMISSIONS_PATH):
                    os.makedirs(SUBMISSIONS_PATH)
                with open(f'SUBMISSIONS_PATH/{submission_id}.zip', 'wb') as f:
                    f.write(submission_zip_resp.content)



    def get_highest_score_submission(self, sid, maxdate=None) -> dict:
        '''
        Get the highest score submission for a student.
        Goes through the whole history of submissions.
        maxdate (optional): datetime object. If provided, only submissions on or before this date will be considered.
        '''
        #  https://www.gradescope.com/courses/569119/assignments/3394470/submissions/202602875.json?content=react&only_keys[]=past_submissions
        submission_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                    '/assignments/'+self.aid+'/submissions/'+sid+'.json?content=react&only_keys[]=past_submissions')

        # now process this json
        submission_json = json.loads(submission_resp.text)

        # loop through all submissions and return the submission with the highest score
        highest_score = 0
        highest_score_submission = None
        for submission in submission_json['past_submissions']:
            date = datetime.fromisoformat(submission['created_at'])
            if maxdate and date > maxdate:
                continue
            if float(submission['score']) >= highest_score:
                highest_score = float(submission['score'])
                highest_score_submission = submission

        return highest_score_submission




    def add_question(self, title, weight, crop = None, content = [], parent_id = None):
        new_q_data = [q.to_patch() for q in self.questions]
        new_crop = crop if crop else [{'x1': 10, 'x2': 91, 'y1': 73, 'y2': 93, 'page_number': 1}]
        new_q = {'title': title, 'weight': weight, 'crop_rect_list': new_crop}
        if parent_id:
            # TODO: This should throw a custom exception if a parent is not found
            parent = [parent for parent in new_q_data if parent['id'] == parent_id][0]
            if parent['children']:
                parent['children'].append(new_q)
            else:
                parent['children'] = [new_q]
        else:
            new_q_data.append(new_q)

        # TODO add id region support
        new_patch = {'assignment': {'identification_regions': {'name': None, 'sid': None}},
                     'question_data': new_q_data}

        outline_resp = self.course.session.get('https://www.gradescope.com/courses/' + self.course.cid +
                                               '/assignments/' + self.aid + '/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')
        authenticity_token = parsed_outline_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        patch_resp = self.course.session.patch('https://www.gradescope.com/courses/' + self.course.cid +
                                               '/assignments/' + self.aid + '/outline/',
                                               headers = {'x-csrf-token': authenticity_token,
                                                          'Content-Type': 'application/json'},
                                               data = json.dumps(new_patch,separators=(',',':')))

        if patch_resp.status_code != requests.codes.ok:
            patch_resp.raise_for_status()

        # TODO this should be done smarter :(
        self.questions = []
        self._lazy_load_questions()

    # TODO allow this to be a predicate remove
    def remove_question(self, title=None, qid=None):
        if not title and not qid:
            return
        new_q_data = [q.to_patch() for q in self.questions]

        # TODO Yes this is slow and ugly, should be improved
        if title: 
            new_q_data = [q for q in new_q_data if q['title'] != title]
            for q in new_q_data:
                if q.get('children'):
                    q['children'] = [sq for sq in q['children'] if sq['title'] != title]
        else:
            new_q_data = [q for q in new_q_data if q['id'] != qid]
            for q in new_q_data:
                if q.get('children'):
                    q['children'] = [sq for sq in q['children'] if sq['id'] != qid]

        new_patch = {'assignment': {'identification_regions': {'name': None, 'sid': None}},
                     'question_data': new_q_data}

        outline_resp = self.course.session.get('https://www.gradescope.com/courses/' + self.course.cid +
                                               '/assignments/' + self.aid + '/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')
        authenticity_token = parsed_outline_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        patch_resp = self.course.session.patch('https://www.gradescope.com/courses/' + self.course.cid +
                                               '/assignments/' + self.aid + '/outline/',
                                               headers = {'x-csrf-token': authenticity_token,
                                                          'Content-Type': 'application/json'},
                                               data = json.dumps(new_patch,separators=(',',':')))

        if patch_resp.status_code != requests.codes.ok:
            patch_resp.raise_for_status()

        # TODO this should be done smarter :(
        self.questions = []
        self._lazy_load_questions()
        
    # TODO INCOMPLETE
    def add_instructor_submission(self, fname):
        '''
        Upload a PDF submission.
        '''
        submission_resp = self.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                           '/assignments/'+self.aid+'/submission_batches')
        parsed_assignment_resp = BeautifulSoup(submission_resp.text, 'html.parser')
        authenticity_token = parsed_assignment_resp.find('meta', attrs = {'name': 'csrf-token'} ).get('content')

        submission_files = {
            "file" : open(template_file, 'rb')
        }

        submission_resp = self.session.post('https://www.gradescope.com/courses/'+self.course.cid+
                                            '/assignments/'+self.aid+'/submission_batches',
                                            files = assignment_files,
                                            headers = {'x-csrf-token': authenticity_token})
        
    # TODO
    def publish_grades(self):
        pass

    # TODO
    def unpublish_grades(self):
        pass

    def _lazy_load_questions(self):        
        outline_resp = self.course.session.get('https://www.gradescope.com/courses/' + self.course.cid +
                                               '/assignments/' + self.aid + '/outline/edit')
        parsed_outline_resp = BeautifulSoup(outline_resp.text, 'html.parser')

        props = parsed_outline_resp.find('div',
                                         attrs={'data-react-class':'AssignmentOutline'}).get('data-react-props')
        json_props = json.loads(props)
        outline = json_props['outline']

        for question in outline:
            qid = question['id']
            title = question['title']
            parent_id = question['parent_id']
            weight = question['weight']
            content = question['content']
            crop = question['crop_rect_list']
            children = []
            qchildren = question.get('children', [])
            
            for subquestion in qchildren:
                c_qid = subquestion['id']
                c_title = subquestion['title']
                c_parent_id = subquestion['parent_id']
                c_weight = subquestion['weight']
                c_content = subquestion['content']
                c_crop = subquestion['crop_rect_list']
                children.append(GSQuestion(c_qid, c_title, c_weight, [], c_parent_id, c_content, c_crop))
            self.questions.append(GSQuestion(qid, title, weight, children, parent_id, content, crop))
            
        
