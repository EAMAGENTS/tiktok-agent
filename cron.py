import os
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler

def run_agent():
    subprocess.run(["python3", "agent.py"])

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_agent, 'cron', hour='*/4')
    scheduler.start()
    print("Cron scheduled - agent runs every 4 hours")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        scheduler.shutdown()
