import os
from flask import Flask, request, render_template, send_file, after_this_request, jsonify, redirect, url_for

app = Flask(__name__)

# Configuración de carpetas y límites
UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER

# Límite máximo para subidas gratuitas de archivos estándar (16 MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Configuración de tarifa para libros o documentos pesados
PRECIO_PESADO_MXN = "20.00"
MONEDA_MXN = "MXN"

# Crear directorios si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Archivo no válido'}), 400

    filename = file.filename
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_path)

    # Simulación/Lógica de conversión
    # (Sustituye esta lógica por la función de librería que uses en tu proyecto)
    output_filename = f"convertido_{os.path.splitext(filename)[0]}.pdf"
    output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)

    try:
        # Aquí va la conversión a PDF...
        with open(output_path, 'wb') as f_out:
            with open(input_path, 'rb') as f_in:
                f_out.write(f_in.read())
    finally:
        # Borrado inmediato del archivo origen para liberar RAM/Disco
        if os.path.exists(input_path):
            os.remove(input_path)

    return jsonify({'download_url': url_for('download_file', filename=output_filename)})


@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)

    # Limpieza automática de la memoria/disco inmediatamente tras entregar la descarga
    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[Auto-Limpieza] Memoria liberada con éxito: {filename}")
        except Exception as e:
            print(f"[Error Auto-Limpieza] No se pudo borrar {filename}: {e}")
        return response

    return send_file(file_path, as_attachment=True)


# Manejo de error cuando el archivo excede los 16 MB
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        'error': 'archivo_pesado',
        'mensaje': 'Tu archivo supera los 16 MB (libro o documento grande). Requiere procesamiento especial.',
        'precio': PRECIO_PESADO_MXN,
        'moneda': MONEDA_MXN
    }), 413


# Creación de orden PayPal para archivos pesados ($20.00 MXN)
@app.route('/create-paypal-order', methods=['POST'])
def create_paypal_order():
    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": MONEDA_MXN,
                "value": PRECIO_PESADO_MXN
            },
            "description": "Conversión de libro / archivo pesado a PDF (>16MB)"
        }]
    }
    # Retorna la configuración lista para ser leída por la API JavaScript de PayPal
    return jsonify(order_data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
