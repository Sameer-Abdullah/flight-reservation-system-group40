# flight-reservation-system-group40
Airline Reservation System project for CP317A

A flask based flight booking web app with support for user accounts, flight search, seat selection, payments, staff based tools, and reminder notifications.

## Requirements
- Python 3.11+ (pip + venv)
- SQLite

## Setup
-- setup of source code:
- git clone https://github.com/Sameer-Abdullah/flight-reservation-system-group40.git
- cd flight-reservation-system-group40


-- Setup environment:
- python -m venv .venv
-macOS/Linux: source .venv/bin/activate
-Windows: .venv\Scripts\activate
-pip install -r requirements.txt

-- To seed the user and staff side databases (Seeding the user database could take a couple minutes):
1.  python -m database.seed or PYTHONPATH=. python3 database/seed.py
2.  python -m database.staff_seed or PYTHONPATH=. python3 database/staff_seed.py


-- To run:
- python run.py
- or from run.py hit run program

- Follow this link to the website (You will see it in output):
 * Running on http://127.0.0.1:5000


-- To login as user:
- Register with any email and enter a password and confirm it.

-- To login as a staff member, either:
1. login with the seeded login credentials:
  -email: sameer-abdullah@skywing.com
  -password: c
2. or register an account with any email ending with @skywing.com as the address.


- To stop the program just hit control c in terminal
