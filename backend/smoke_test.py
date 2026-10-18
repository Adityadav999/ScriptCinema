import sys, tempfile, os, shutil
sys.path.insert(0, '.')
from services.project_detector import detect_project, _w, _python, _pip

tmp = tempfile.mkdtemp()
pkg = '{"dependencies":{"next":"14.0.0","react":"18.0.0"},"scripts":{"dev":"next dev"}}'
with open(os.path.join(tmp, 'package.json'), 'w') as f:
    f.write(pkg)

try:
    cfg = detect_project(tmp)
    print('Detected:', cfg.project_type)
    print('Port:', cfg.port)
    print('ENV PORT:', cfg.env_vars.get('PORT'))
    print('Start cmd:', cfg.start_cmd)
    print('npm resolved:', _w('npm'))
    print('python:', _python())
    print('pip:', _pip())
    print('ALL OK')
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
