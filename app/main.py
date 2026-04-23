import os
import requests
import zipfile
import io
from openai import OpenAI

# -------- CONFIG --------
repo = os.environ["REPO"]
run_id = os.environ["RUN_ID"]
token = os.environ["GITHUB_TOKEN"]

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# -------- STEP 1: DOWNLOAD LOGS --------
def download_logs():
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/logs"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers)
    z = zipfile.ZipFile(io.BytesIO(r.content))

    logs = ""
    for file in z.namelist():
        with z.open(file) as f:
            logs += f.read().decode("utf-8", errors="ignore") + "\n"

    return logs

# -------- STEP 2: FILTER LOGS --------
def extract_relevant_logs(log_text):
    keywords = ["error", "failed", "exception"]
    lines = log_text.split("\n")

    filtered = [l for l in lines if any(k in l.lower() for k in keywords)]

    # fallback if nothing matched
    if not filtered:
        return "\n".join(lines[-200:])

    return "\n".join(filtered[-200:])

# -------- STEP 3: CALL LLM --------
def analyze_logs(logs):
    prompt = f"""
You are a senior DevOps engineer.

Analyze the CI/CD failure logs.

Return:
- Root cause
- Category
- Fix
- Confidence (low/medium/high)

Logs:
{logs}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Expert DevOps engineer"},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content

# -------- STEP 4: FIND PR (IMPORTANT FIX) --------
def get_pr_number():
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers).json()

    prs = r.get("pull_requests", [])
    if prs:
        return prs[0]["number"]

    return None

# -------- STEP 5: POST COMMENT --------
def post_comment(message):
    pr_number = get_pr_number()

    headers = {"Authorization": f"Bearer {token}"}

    if pr_number:
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    else:
        # fallback to commit comment
        url = f"https://api.github.com/repos/{repo}/issues/{run_id}/comments"

    requests.post(url, json={"body": message}, headers=headers)

# -------- MAIN --------
def main():
    print("Downloading logs...")
    logs = download_logs()

    print("Filtering logs...")
    relevant_logs = extract_relevant_logs(logs)

    print("Analyzing logs with AI...")
    result = analyze_logs(relevant_logs)

    message = f"🤖 **AI CI Failure Debugger**\n\n{result}"

    print("Posting result...")
    post_comment(message)

    print("Done!")

if __name__ == "__main__":
    main()