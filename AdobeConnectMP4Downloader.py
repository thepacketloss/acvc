'''
Adobe connect merge and convert videos to mp4
requirements : requests, tqdm, ffmpeg
install with "pip install requests tqdm"
by Masoud Moradjafari
'''

import glob
import os
import requests
import shlex
import shutil
import subprocess
import zipfile
from tqdm import *
from urllib3.exceptions import InsecureRequestWarning
from xml.etree import ElementTree

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
email = ''
password = ''
meeting_url = input("Enter meeting url (Example : http://example.com/xxxxxxxxxxx) : ").strip().rstrip('/')
meeting_id = meeting_url.split('/')[-1]
meeting_url = meeting_url.replace(f'/{meeting_id}', '')


def run_command(command):
    try:
        print('running command: {0}'.format(command))
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        while True:
            output = process.stdout.readline()
            print(output.strip())
            if output == b'' and process.poll() is not None:
                print('Done running the command.')
                break
            if output:
                print(output.strip())
        rc = process.poll()
        return rc
    except Exception as e:
        print(f'Running command failed : {e}')


def main():
    try:
        f = open("session.txt", "r")
        session_token = f.readline()
        f.close()
        with requests.get(
                f'{meeting_url}/{meeting_id}/output/filename.zip?download=zip&session={session_token}',
                stream=True, verify=False) as r:
            r.raise_for_status()
            with open(f"{meeting_id}.zip", 'wb') as f:
                pbar = tqdm(total=int(r.headers['Content-Length']))
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        with zipfile.ZipFile(f'{meeting_id}.zip', 'r') as zip_ref:
            zip_ref.extractall(meeting_id)

        cameraVoip_filepaths = []
        for filepaths in sorted(glob.glob(os.path.join(meeting_id, 'cameraVoip_*.flv'))):
            cameraVoip_filepaths.append(filepaths)
        screenshare_filepaths = []
        for filepaths in sorted(glob.glob(os.path.join(meeting_id, 'screenshare_*.flv'))):
            screenshare_filepaths.append(filepaths)

        if len(cameraVoip_filepaths) == 0 or len(screenshare_filepaths) == 0:
            print('No video or audio found!')
            exit(0)

        part = 0
        output_filepaths = []
        os.mkdir(f'{meeting_id}_out')
        for cameraVoip_filepath, screenshare_filepath in zip(cameraVoip_filepaths, screenshare_filepaths):
            output_filepath = os.path.join(f'{meeting_id}_out', '{0}_{1:04d}.flv'.format(meeting_id, part))
            output_filepaths.append(output_filepath)
            conversion_command = 'ffmpeg -i "%s" -i "%s" -c copy -map 0:a:0 -map 1:v:0 -shortest -y "%s"' % (
                cameraVoip_filepath, screenshare_filepath, output_filepath)
            run_command(conversion_command)
            part += 1
        video_list_filename = 'video_list.txt'
        video_list_file = open(video_list_filename, 'w')
        for output_filepath in output_filepaths:
            video_list_file.write("file '{0}'\n".format(output_filepath))
        video_list_file.close()
        final_output_filepath = '{0}.flv'.format(meeting_id)
        conversion_command = 'ffmpeg -safe 0 -y -f concat -i "{1}" -c copy "{0}"'.format(final_output_filepath,
                                                                                         video_list_filename)
        run_command(conversion_command)
        run_command(f'ffmpeg -i {meeting_id}.flv {meeting_id}.mp4')
        os.remove(f'{meeting_id}.zip')
        os.remove(f'{meeting_id}.flv')
        os.remove("video_list.txt")
        shutil.rmtree(meeting_id)
        shutil.rmtree(f'{meeting_id}_out')
        print('DONE!')
    except Exception as e:
        print(f'Operation failed : {e}')


if os.path.exists('session.txt'):
    try:
        f = open("session.txt", "r")
        session_token = f.readline()
        f.close()
        is_logged_in = requests.get(f'{meeting_url}/api/xml?action=principal-list&session={session_token}',
                                    verify=False)
        if ElementTree.fromstring(is_logged_in.content)[0].attrib['code'] == 'no-access':
            os.remove('session.txt')
            print('Your session is expired. please re-run the script!')
        else:
            main()
    except Exception as e:
        print(f'Check user login failed : {e}')
else:
    try:
        email = input("Enter email : ").strip()
        password = input("Enter password : ").strip()
        cookie_res = requests.get(f'{meeting_url}/api/xml?action=common-info', verify=False)
        session = ElementTree.fromstring(cookie_res.content)[2][0].text
        file = open('session.txt', 'w+')
        file.write(session)
        file.close()
        login_res = requests.get(
            f'{meeting_url}/api/xml?action=login&login={email}&password={password}&session={session}',
            verify=False)
        if login_res.status_code == 200:
            main()
        else:
            print('Login failed :(')
    except Exception as e:
        print(f'Login failed : {e}')
