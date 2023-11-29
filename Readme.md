# Readme

This project contains scripts that can be used for logistical TA work for managing a massive programming course in TAMU: CSCE120/121. 

For now, we have a script for automatically processing excused absence requests. The excused absence requests are received through a Google Form that collects student information and the reason for absence, and stores it in a Google Sheet. 
This script currently processes only the HW absence requests (and not other types of requests).
The HW absence records are stored in a Canvas assignment. The homeworks are submitted on Gradescope. 

For late homeworks, the students submit their homework on a "Redemption" assignment on Gradescope. Our processing a late homework request, our job is to download the highest scoring late submission from the "Redemption" assignment on Gradescope, calculate the number of late days, check if the late days are within the limit (not more than 4; and in total not more than 10), re-upload the submission to the actual Gradescope assignment, and then update the late score on Canvas (alongwith comments).

This script does all this automatically. 
It reads the Google Sheet, checks which request is to be processed, transfers the gradescope submissions (with requisite checking), waits for the submission to be graded (making sure that the submission gets the same score as the one on the "Redemption" assignment), and then updates the Canvas gradebook.

## Usage

### Keys and such
First of all, before running the script, you need to have the following with you:
- a Canvas Access Token, 
- your Gradescope username and password,
- [OPTIONAL] a Google API Key (this is optional because if you don't have a Google API Key, you can just download the Google Sheet as a CSV file named "absence.csv" and place it in the same folder as the script).

For the Canvas Access Token, go to Canvas, and then go to Account > Settings > Approved Integrations > New Access Token. 
Add some purpose, leave the expiry date blank, and then click on "Generate Token". Copy the token and save it somewhere (you won't be able to see it again; hence make sure you save it somewhere).

For Google API key, go to https://console.developers.google.com/apis/credentials, and create a new OAuth 2.0 Client ID, and download the JSON file and save it as `google_credentials.json` in the same folder as the script.

### Running the script

First, install the requirements:

```bash
pip install -r requirements.txt
```

Then, run the script:

```bash
python absence_processing.py
```

## Acknowledgements

For this script, we utilized the official APIs of Google Sheets and Canvas, which are very well developed and documented.

Unfortunately, Gradescope does not have an official API.
For the Gradescope API, we'd like to thank the following repository for providing some basic reverse-engineering of the Gradescope API: https://github.com/apozharski/gradescope-api.
However, we had to make several changes to this code in order to make the API work. Note that this is currently a very hacky work, and if Gradescope changes their interface, this API will break.

Our modified version of the Gradescope API is available in the `gradescope_api` folder.

