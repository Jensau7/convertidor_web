import os
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_file, jsonify, session, redirect, url_for, make_response
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'convertidor_expres_pro_secret_key_noe'

UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

def init_user_session():
    if 'free_trial_used' not in session:
        session['free_trial_used'] = False
    if 'credits' not in session:
        session['credits'] = 0
    if 'platinum_until' not in session:
        session['platinum_until'] = None

def is_platinum_active():
    if session.get('platinum_until'):
        try:
            exp_date = datetime.fromisoformat(session['platinum_until'])
            if datetime.utcnow() < exp_date:
                return True
            else:
                session['platinum_until'] = None
        except Exception:
            session['platinum_until'] = None
    return False

@app.route('/')
def index():
    init_user_session()
    pago_exitoso = session.pop('pago_exitoso', False)
    return render_template(
        'index.html',
        free_trial_available=not session['free_trial_used'],
        credits=session.get('credits', 0),
        is_platinum=is_platinum_active(),
        platinum_until=session.get('platinum_until'),
        pago_exitoso=pago_exitoso
    )

@app.route('/convert', methods=['POST'])
def convert_file():
    init_user_session()

    if 'file' not in request.files:
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Archivo no válido'}), 400

    if is_platinum_active():
        pass
    elif not session['free_trial_used']:
        session['free_trial_used'] = True
    elif session.get('credits', 0) > 0:
        session['credits'] -= 1
    else:
        return jsonify({
            'error': 'payment_required',
            'mensaje': 'Has agotado tu prueba gratuita. Selecciona una opción para continuar.'
        }), 402

    filename = file.filename
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_path)

    base_name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext in ['.txt', '.log']:
            # Devolver archivo .txt limpio automáticamente
            output_filename = f"convertido_{base_name}.txt"
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            mimetype_out = 'text/plain'

            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f_in:
                content = f_in.read()
            with open(output_path, 'w', encoding='utf-8') as f_out:
                f_out.write(content)

        elif ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
            # Convertir imagen a PDF automáticamente
            output_filename = f"convertido_{base_name}.pdf"
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            mimetype_out = 'application/pdf'

            with Image.open(input_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(output_path, "PDF", resolution=100.0)
        else:
            return jsonify({'error': 'Formato no compatible. Sube imágenes (.jpg, .png) o texto (.txt).'}), 400

        response = make_response(send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype=mimetype_out
        ))
        
        response.set_cookie('download_complete', output_filename, max_age=60)
        return response

    except Exception as e:
        print(f"[Error de Conversión]: {e}")
        return jsonify({'error': 'No se pudo procesar el archivo'}), 500
    finally:
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except Exception:
                pass

@app.route('/confirm-download-complete', methods=['POST'])
def confirm_download_complete():
    data = request.get_json() or {}
    filename = data.get('filename')

    if filename:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(app.config['CONVERTED_FOLDER'], safe_filename)

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return jsonify({'status': 'deleted', 'file': safe_filename}), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    return jsonify({'status': 'file_not_found'}), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        'error': 'archivo_pesado',
        'mensaje': 'Tu archivo supera los 16 MB. Se requiere un pago de $20 MXN para procesarlo.'
    }), 413

@app.route('/activar-plan/<plan_type>')
def activar_plan(plan_type):
    init_user_session()

    if plan_type == 'single':
        session['credits'] = session.get('credits', 0) + 1
    elif plan_type == 'pack':
        session['credits'] = session.get('credits', 0) + 10
    elif plan_type == 'platinum':
        exp_date = datetime.utcnow() + timedelta(days=30)
        session['platinum_until'] = exp_date.isoformat()
    elif plan_type == 'heavy':
        session['credits'] = session.get('credits', 0) + 1

    session['pago_exitoso'] = True
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
