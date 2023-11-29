# Readme

This project contains scripts that can be used for logistical TA work for managing a massive programming course in TAMU: CSCE120/121. 

For now, we have a script for automatically processing excused absence requests. The excused absence requests are received through a Google Form that collects student information and the reason for absence, and stores it in a Google Sheet. 
This script currently processes only the HW absence requests (and not other types of requests).
The HW absence records are stored in a Canvas assignment. The homeworks are submitted on Gradescope. 

For late homeworks, the students submit their homework on a "Redemption" assignment on Gradescope. Our processing a late homework request, our job is to download the highest scoring late submission from the "Redemption" assignment on Gradescope, calculate the number of late days, check if the late days are within the limit (not more than 4; and in total not more than 10), re-upload the submission to the actual Gradescope assignment, and then update the late score on Canvas (alongwith comments).

This script does all this automatically. 
It reads the Google Sheet, checks which request is to be processed, transfers the gradescope submissions (with requisite checking), waits for the submission to be graded (making sure that the submission gets the same score as the one on the "Redemption" assignment), and then updates the Canvas gradebook.

## Usage

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
