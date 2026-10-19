import os
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_file, after_this_request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'convertidor_expres_pro_secret_key_noe'

UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER

# Límite para subida estándar: 16 MB
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
        exp_date = datetime.fromisoformat(session['platinum_until'])
        if datetime.utcnow() < exp_date:
            return True
        else:
            session['platinum_until'] = None
    return False


@app.route('/')
def index():
    init_user_session()
    return render_template(
        'index.html',
        free_trial_available=not session['free_trial_used'],
        credits=session.get('credits', 0),
        is_platinum=is_platinum_active(),
        platinum_until=session.get('platinum_until')
    )


@app.route('/convert', methods=['POST'])
def convert_file():
    init_user_session()

    if 'file' not in request.files:
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Archivo no válido'}), 400

    has_permission = False

    if is_platinum_active():
        has_permission = True
    elif not session['free_trial_used']:
        session['free_trial_used'] = True
        has_permission = True
    elif session.get('credits', 0) > 0:
        session['credits'] -= 1
        has_permission = True
    else:
        return jsonify({
            'error': 'payment_required',
            'mensaje': 'Has agotado tu prueba gratuita. Selecciona una opción para continuar.'
        }), 402

    filename = file.filename
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_path)

    output_filename = f"convertido_{os.path.splitext(filename)[0]}.pdf"
    output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)

    try:
        with open(output_path, 'wb') as f_out:
            with open(input_path, 'rb') as f_in:
                f_out.write(f_in.read())
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

    return jsonify({'download_url': url_for('download_file', filename=output_filename)})


@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)

    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[Auto-Limpieza] Memoria liberada: {filename}")
        except Exception as e:
            print(f"[Error Auto-Limpieza] No se pudo borrar {filename}: {e}")
        return response

    return send_file(file_path, as_attachment=True)


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        'error': 'archivo_pesado',
        'mensaje': 'Tu archivo supera los 16 MB (libro o documento grande). Se requiere un pago de $20 MXN para procesarlo.',
        'precio': '20.00',
        'moneda': 'MXN'
    }), 413


@app.route('/create-paypal-order', methods=['POST'])
def create_paypal_order():
    data = request.get_json() or {}
    plan_type = data.get('plan', 'single')

    precios = {
        'single': ('2.00', '1 Conversión Individual (<16MB)'),
        'pack': ('10.00', 'Paquete de 10 Conversiones (<16MB)'),
        'platinum': ('100.00', 'Membresía Platinum - 1 Mes Ilimitado'),
        'heavy': ('20.00', 'Conversión de Libro / Archivo Pesado (>16MB)')
    }

    precio, desc = precios.get(plan_type, ('2.00', '1 Conversión Individual'))

    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "MXN",
                "value": precio
            },
            "description": desc
        }]
    }
    return jsonify(order_data)


@app.route('/capture-paypal-order', methods=['POST'])
def capture_paypal_order():
    data = request.get_json() or {}
    plan_type = data.get('plan')

    init_user_session()

    if plan_type == 'single':
        session['credits'] = session.get('credits', 0) + 1
    elif plan_type == 'pack':
        session['credits'] = session.get('credits', 0) + 10
    elif plan_type == 'platinum':
        exp_date = datetime.utcnow() + timedelta(days=30)
        session['platinum_until'] = exp_date.isoformat()

    return jsonify({'status': 'success', 'credits': session.get('credits', 0), 'is_platinum': is_platinum_active()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
