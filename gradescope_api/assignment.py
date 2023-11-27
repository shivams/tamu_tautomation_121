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
                '''
                 'assignment_submission': {'active': True,
                                           'created_at': '2023-11-25T08:25:54.494897-08:00',
                                           'export_allowed': True,
                                           'id': 215243878,
                                           'lateness_in_words': '42 Days, 10 Hours Late',
                                           'score': '40.75',
                                           'source': 'web',
                                           'start_time_utility_submission': False,
                                           'status': 'processed'},
                 'course_members': [{'email': 'jackastevenson@tamu.edu',
                                     'id': 4055195,
                                     'name': 'Jack Stevenson'}],
                '''
                #  import ipdb; ipdb.set_trace()
                score = submission_json['assignment_submission']['score']
                time = datetime.fromisoformat(submission_json['assignment_submission']['created_at'])
                submission_id = submission_json['assignment_submission']['id']
                name = submission_json['course_members'][0]['name']
                email = submission_json['course_members'][0]['email']
                if score:
                    break
            except:
                sleep(5) # wait 5 seconds before trying again

        return GSSubmission(subid=submission_id, name=name, email=email, score=score,
                            time=time, student_id=student_id, assignment=self)



    def get_submission(self, email):
        '''
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
                submission = self.get_highest_score_submission(submission_id)
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

        '''
        <table class="table js-reviewGradesTable">
        <thead>
        <tr>
            <th class="js-firstLastName">First & Last Name <div class="table--headingButtonContainer js-swapNameColumns"> <button class= "tiiBtn tiiBtn-tertiary tiiBtn-extraSmall">Swap</button></div> </th>
            <th class="js-lastFirstName">Last, First Name <div class="table--headingButtonContainer js-swapNameColumns"> <button class= "tiiBtn tiiBtn-tertiary tiiBtn-extraSmall">Swap</button></div> </th>
            <th>Email</th>
            <th class="js-sections">Sections</th>
            <th class="u-centeredText"><span aria-label="Score out of 100.0" role="region">Score/100.0</span></th>
            <th class="u-centeredText">Graded?</th>
            <th class="u-centeredText">Viewed?</th>
            <th class="u-centeredText">Canvas</th>
            <th>Time (<abbr title= "Central Time (US &amp; Canada)">CST</abbr>)</th>
        </tr>
        </thead>
        <tbody>
        <tr>
            <td class="table--primaryLink"><a class="link-gray" href= "/courses/569119/assignments/3394470/submissions/199538676">Nikola Slavchev</a></td>
            <td class="table--primaryLink"><a class="link-gray" href= "/courses/569119/assignments/3394470/submissions/199538676">Slavchev, Nikola</a></td>
            <td><a href="mailto:nislavch@tamu.edu">nislavch@tamu.edu</a></td>
            <td></td>
            <td class="u-centeredText" data-sort="1.0">100.0</td>
            <td class="u-centeredText statusIcon-active" data-sort="1"></td>
            <td class="u-centeredText statusIcon-inactive" data-sort="0"> <span aria-hidden="true">--</span><span class="sr-only">Submission has not been viewed.</span></td>
            <td class="u-centeredText" data-sort="1"></td>
            <td data-sort="2023-10-04 19:57:16 -0500"><time datetime= "2023-10-04 19:57:16 -0500">Oct 04 at 7:57PM</time></td>
        </tr>
        <tr>
            <td>Ernesto Fuentes Hernandez</td>
            <td>Fuentes Hernandez, Ernesto</td>
            <td><a href= "mailto:ernesto_fuentes12@tamu.edu">ernesto_fuentes12@tamu.edu</a></td>
            <td> <div class="sectionsColumnCell"> <div class="sectionsColumnCell--section"><span class= "sectionsColumnCell--sectionSpan" title= "csce-121-505">csce-121-505</span></div> </div> </td>
            <td class="table--hiddenColumn"></td>
            <td class="u-centeredText" colspan="6" data-sort="-1">This student doesn't have a submission.</td>
            <td class="table--hiddenColumn" data-sort="-1"></td>
            <td class="table--hiddenColumn" data-sort="-1"></td>
            <td class="table--hiddenColumn"></td>
        </tr>
        <tr>
            <td class="table--primaryLink"><a class="link-gray" href= "/courses/569119/assignments/3394470/submissions/215194755">Carson Burkhart</a></td>
            <td class="table--primaryLink"><a class="link-gray" href= "/courses/569119/assignments/3394470/submissions/215194755">Burkhart, Carson</a></td>
            <td><a href= "mailto:ctburkhart@tamu.edu">ctburkhart@tamu.edu</a></td>
            <td> <div class="sectionsColumnCell"> <div class="sectionsColumnCell--section"><span class= "sectionsColumnCell--sectionSpan" title= "csce-121-502">csce-121-502</span></div> </div> </td>
            <td class="u-centeredText" data-sort="0.78">78.0</td>
            <td class="u-centeredText statusIcon-active" data-sort="1"></td>
            <td class="u-centeredText statusIcon-inactive" data-sort="0"> <span aria-hidden="true">--</span><span class="sr-only">Submission has not been viewed.</span></td>
            <td class="u-centeredText" data-sort="1"></td>
            <td data-sort="2023-11-24 13:42:18 -0600"><time datetime= "2023-11-24 13:42:18 -0600">Nov 24 at 1:42PM</time></td>
        </tr>
        </tbody>
        </table>
        '''

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
            #  score = row.find_all('td')[4].text
            #  time = row.find_all('td')[8].text

            submission = self.get_highest_score_submission(submission_id)
            # Sample submission:
            #  {
              #  "id": 202602831,
              #  "created_at": "2023-10-14T01:45:50.720687-07:00",
              #  "owners": [
                #  {
                  #  "id": 4077592,
                  #  "active": false,
                  #  "initials": "RDCL",
                  #  "name": "Roberto Del Callejo Lopez"
                #  }
              #  ],
              #  "show_path": "/courses/569119/assignments/3394470/submissions/202602831",
              #  "active": false,
              #  "activate_path": "/courses/569119/assignments/3394470/submissions/202602831/activate",
              #  "can_activate": true,
              #  "score": "88.75"
            # }

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



    def get_highest_score_submission(self, sid) -> dict:
        '''
        Get the highest score submission for a student.
        Goes through the whole history of submissions.
        '''
        #  https://www.gradescope.com/courses/569119/assignments/3394470/submissions/202602875.json?content=react&only_keys[]=past_submissions
        submission_resp = self.course.session.get('https://www.gradescope.com/courses/'+self.course.cid+
                                                    '/assignments/'+self.aid+'/submissions/'+sid+'.json?content=react&only_keys[]=past_submissions')
        # this returns a json in the following form:
        '''
        {
          "past_submissions": [
            {
              "id": 202602875,
              "created_at": "2023-10-14T01:47:12.746147-07:00",
              "owners": [
                {
                  "id": 4077592,
                  "active": true,
                  "initials": "RDCL",
                  "name": "Roberto Del Callejo Lopez"
                }
              ],
              "show_path": "/courses/569119/assignments/3394470/submissions/202602875",
              "active": false,
              "activate_path": "/courses/569119/assignments/3394470/submissions/202602875/activate",
              "can_activate": true,
              "score": "89.0"
            },
            {
              "id": 202602831,
              "created_at": "2023-10-14T01:45:50.720687-07:00",
              "owners": [
                {
                  "id": 4077592,
                  "active": false,
                  "initials": "RDCL",
                  "name": "Roberto Del Callejo Lopez"
                }
              ],
              "show_path": "/courses/569119/assignments/3394470/submissions/202602831",
              "active": false,
              "activate_path": "/courses/569119/assignments/3394470/submissions/202602831/activate",
              "can_activate": true,
              "score": "88.75"
            },
          ],
          "alert": null
        }
        '''

        # now process this json
        submission_json = json.loads(submission_resp.text)

        # loop through all submissions and return the submission with the highest score
        highest_score = 0
        highest_score_submission = None
        for submission in submission_json['past_submissions']:
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
            
        
