from flask import Flask, request, send_file
import outline
import outline.cuerun
import outline.modules.shell
import getpass
import waitress
from werkzeug.utils import secure_filename
import os
import shutil
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def build_layer(layer_data, command, last_layer=None):

    threadable = float(layer_data.get('cores')) >= 2
    layer = outline.modules.shell.Shell(
        layer_data.get('name'), command=command.split(), chunk=layer_data.get('chunk'),
        threads=float(layer_data.get('cores')), range=layer_data.get('layerRange'), threadable=threadable)
    layer.set_service([])
    layer.set_limits([])

    if layer_data.get('dependType') and last_layer:
        if layer_data.get('dependType') == 'Layer':
            layer.depend_all(last_layer)
        else:
            layer.depend_on(last_layer)
            
    return layer


def build_shell_layer(layer_data, last_layer, shot):
    cmd = f'/usr/local/blender/blender -b -noaudio /tmp/rqd/shots/{layer_data.get("file_3d")} -o /tmp/rqd/shots/{shot}/{shot}.##### -F JPEG -f #IFRAME#'
    return build_layer(layer_data, cmd, last_layer)

def submit_job(job_data):
    ol = outline.Outline(
        job_data.get('name'), shot=job_data.get('shot'), show=job_data.get('show'), user=getpass.getuser())
    last_layer = None
    for layer_data in job_data.get('layers'):
        layer = build_shell_layer(layer_data, last_layer, job_data.get('shot'))
        ol.add_layer(layer)
        last_layer = layer
        
    if 'facility' in job_data:
        ol.set_facility(None)

    return outline.cuerun.launch(ol, use_pycuerun=False)


@app.post("/")
def index():
    try:
        body = request.get_json()
        shot_dir = '/tmp/rqd/shots/'
        shot_path = os.path.join(shot_dir, body.get('shot'))
        os.makedirs(shot_path)
        
        submit_job(body)
    except Exception as e:
        return {
            'success': False,
            'message': e
        }

    return {
        'success': True,
        'message': "job has successfully running",
        'data': body
    }


@app.post('/upload')
def upload():
    if 'file' not in request.files:
        return {
            'success': False,
            'message': 'upload filenya gan'
        }
    file = request.files['file']
    if file :
        filename = secure_filename(file.filename)
        shot_dir = '/tmp/rqd/shots/'
        shot_path = os.path.join(shot_dir, filename)
        file.save(shot_path)
    return {
        'success': True,
        'message': 'upload file success',
    }


@app.get('/download/<path:filename>')
def download(filename):
    shot_dir = '/tmp/rqd/shots/'
    shot_path = os.path.join(shot_dir, filename)
    archive = shutil.make_archive(filename, 'zip', shot_path)
    return send_file(archive, as_attachment=True)

@app.get('/check/<path:shot_name>')
def check(shot_name):
    total_frame = request.args.get('total_frame')
    shot_dir = '/tmp/rqd/shots/'
    shot_path = os.path.join(shot_dir, shot_name)
    if os.path.exists(shot_path):
        files = os.listdir(shot_path)
        if len(files) == total_frame:
            return {
                'success': True,
                'message': 'check completed',
                'data': {
                    'status': 'complete'
                }
            }

        return {
            'success': True,
            'message': 'check completed',
            'data': {
                'status': 'running'
            }
        }
    else:
        return {
            'success': False,
            'message': 'folder not exist',
            'data': {
                'status': 'error'
            }
        }

if __name__ == '__main__':
    waitress.serve(app, host='0.0.0.0', port='5000')