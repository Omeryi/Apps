# Key-Value Datastore Service

A simple key-value database web service built with Flask, running on Google App Engine Standard (Python 3), and persisted in Google Cloud Datastore.

## API Endpoints

All endpoints use HTTP `GET` and return plain text responses.

- `/set?name={variable_name}&value={variable_value}`
  - Sets or updates a variable.
  - Response example: `x = 10`
- `/get?name={variable_name}`
  - Gets the variable value.
  - Returns `None` if not set.
- `/unset?name={variable_name}`
  - Removes a variable.
  - Response example: `x = None`
- `/numequalto?value={variable_value}`
  - Returns the number of variables currently equal to the given value.
- `/undo`
  - Reverts the most recent `SET` or `UNSET`.
  - Returns `NO COMMANDS` if nothing can be undone.
- `/redo`
  - Re-applies the most recently undone command.
  - Returns `NO COMMANDS` if nothing can be redone.
- `/history`
  - Returns recent modifying commands (`SET` and `UNSET`) in execution order.
  - Example:
    - `SET a 10`
    - `SET b 20`
    - `UNSET a`
- `/end`
  - Clears all stored data.
  - Response: `CLEANED`

## Why `/history` Improves the App

`/history` provides a quick audit/debug trail of recent data mutations. It helps track what changed and in which order, which is useful when investigating unexpected state or validating workflows.

## Run Locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Set Google Cloud credentials so Datastore is accessible:
   - `set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account.json` (Windows PowerShell/cmd equivalent)
3. Run the app:
   - `python main.py`
4. Service default URL:
   - `http://localhost:8080`

## Deploy to Google App Engine

1. Authenticate and select your project:
   - `gcloud auth login`
   - `gcloud config set project YOUR_PROJECT_ID`
2. Deploy:
   - `gcloud app deploy`
3. Open the service:
   - `gcloud app browse`

Deployed URL format:

- `https://your-app-id.appspot.com`

## Run Automated Tests

1. Install requests if needed:
   - `pip install requests`
2. Update base URL in `test_sequences.py` or set an environment variable:
   - `set BASE_URL=https://your-app-id.appspot.com`
3. Run:
   - `python test_sequences.py`

The script prints every request/response and stops immediately with a clear error if any assertion fails.
