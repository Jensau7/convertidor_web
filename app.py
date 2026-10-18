import os
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from PIL import Image
import openpyxl
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_convertidor'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def convertir_imagen_a_pdf(input_path, output_pdf):
    img = Image.open(input_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(output_pdf, "PDF", resolution=100.0)

def convertir_xlsx_a_pdf(input_path, output_pdf):
    wb = openpyxl.load_workbook(input_path)
    sheet = wb.active
    c = canvas.Canvas(output_pdf, pagesize=letter)
    width, height = letter
    y = height - 50
    c.drawString(50, y, f"--- Hoja: {sheet.title} ---")
    y -= 25
    for row in sheet.iter_rows(values_only=True):
        fila_texto = " | ".join([str(val) for val in row if val is not None])
        if fila_texto.strip():
            if y < 50:
                c.showPage()
                y = height - 50
            c.drawString(50, y, fila_texto[:90])
            y -= 15
    c.save()

def convertir_txt_a_pdf(input_path, output_pdf):
    c = canvas.Canvas(output_pdf, pagesize=letter)
    width, height = letter
    y = height - 50
    with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            linea = line.strip()
            if linea:
                if y < 50:
                    c.showPage()
                    y = height - 50
                c.drawString(50, y, linea[:85])
                y -= 15
    c.save()

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'usos_gratis' not in session:
        session['usos_gratis'] = 0
        
    es_vip = session.get('es_vip', False)

    if request.method == 'POST':
        if session['usos_gratis'] >= 1 and not es_vip:
            return render_template('index.html', bloqueado=True, usos=session['usos_gratis'])

        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file:
            filename = file.filename
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_path)
            
            output_pdf_name = f"Convertido_{os.path.splitext(filename)[0]}.pdf"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_pdf_name)
            
            ext = filename.lower()
            if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                convertir_imagen_a_pdf(input_path, output_path)
            elif ext.endswith('.xlsx'):
                convertir_xlsx_a_pdf(input_path, output_path)
            elif ext.endswith('.txt'):
                convertir_txt_a_pdf(input_path, output_path)
            else:
                return "Formato no soportado", 400

            if not es_vip:
                session['usos_gratis'] += 1
                
            return send_file(output_path, as_attachment=True)
            
    return render_template('index.html', bloqueado=(session['usos_gratis'] >= 1 and not es_vip), usos=session['usos_gratis'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
