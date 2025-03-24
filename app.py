from flask import Flask, render_template, request, redirect, url_for, session
from flask import flash
from flask_wtf.csrf import CSRFProtect
from config import DevelopmentConfig
from flask import g
from forms import PizzaForm, ClienteForm, LoginForm
from models import db
from models import Venta, DetallePizza, IngredientePizza, Usuario
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
import json

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))  

PRECIOS = {
    'pequena': 40,
    'mediana': 80,
    'grande': 120
}

COSTO_INGREDIENTE = 10


def agregarPizza(tamano, cantidad, ingredientes):
    ingredientes_lista = ",".join(ingredientes)
    with open("pedidos.txt", "a", encoding="utf-8") as archivo:
        archivo.write(f"{tamano}|{cantidad}|{ingredientes_lista}\n")


def cargarCarrito():
    carrito = []
    try:
        with open("pedidos.txt", "r", encoding="utf-8") as archivo:
            for linea in archivo:
                datos = linea.strip().split("|")
                if len(datos) >= 3:
                    carrito.append({
                        "tamano": datos[0],
                        "cantidad": datos[1],
                        "ingredientes": datos[2].split(",") if datos[2] else []
                    })
    except FileNotFoundError:
        with open("pedidos.txt", "w", encoding="utf-8") as archivo:
            pass
    return carrito


def eliminarPizzaEspecifica(indice):
    carrito = cargarCarrito()
    if 0 <= indice < len(carrito):
        carrito.pop(indice)
        with open("pedidos.txt", "w", encoding="utf-8") as archivo:
            for pizza in carrito:
                ingredientes_lista = ",".join(pizza["ingredientes"])
                archivo.write(
                    f"{pizza['tamano']}|{pizza['cantidad']}|{ingredientes_lista}\n")
        return True
    return False


def vaciarCarrito():
    open("pedidos.txt", "w").close()


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(user=form.user.data).first()
        if usuario:
            if usuario.contrasenia == form.contrasenia.data:
                login_user(usuario)
                flash('Bienvenido')
                return redirect(url_for('index'))
            else: 
                flash('Contraseña incorrecta')
        else:
            flash('Usuario incorrecto')
    return render_template('login.html', form=form)

@app.route("/logout", methods=['POST', 'GET'])
@login_required
def logout():
    logout_user()
    flash('Finalizaste sesión')
    return redirect(url_for('login'))

@app.route("/", methods=['GET', 'POST'])
@login_required
def index():
    pizza_form = PizzaForm()
    cliente_form = ClienteForm()

    if 'cliente_data' in session:
        cliente_form.nombre.data = session['cliente_data'].get('nombre', '')
        cliente_form.direccion.data = session['cliente_data'].get(
            'direccion', '')
        cliente_form.telefono.data = session['cliente_data'].get(
            'telefono', '')

    if request.method == 'POST' and pizza_form.validate_on_submit():
        session['cliente_data'] = {
            'nombre': cliente_form.nombre.data,
            'direccion': cliente_form.direccion.data,
            'telefono': cliente_form.telefono.data
        }

        if not pizza_form.ingredientes.data:
            flash('Debes seleccionar al menos un ingrediente', 'danger')
            return redirect(url_for('index'))

        agregarPizza(pizza_form.tamano.data, pizza_form.numPizzas.data,
                     pizza_form.ingredientes.data)
        flash('Pizza agregada al carrito', 'success')
        return redirect(url_for('index'))

    carrito = cargarCarrito()

    ventas_hoy = []
    try:
        ventas_hoy = Venta.query.filter(db.func.date(
            Venta.fecha) == db.func.current_date()).all()
    except:
        ventas_hoy = []

    suma_total = sum(venta.total_venta for venta in ventas_hoy)

    return render_template('index.html', pizza_form=pizza_form, cliente_form=cliente_form, carrito=carrito, ventas_hoy=ventas_hoy, suma_total=suma_total)


@app.route('/finalizarPedido', methods=['GET', 'POST'])
def finalizarPedido():
    cliente_form = ClienteForm()
    pizzas = cargarCarrito()

    if not pizzas:
        flash("No hay pizzas en el carrito", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        if cliente_form.validate_on_submit():
            nombre = cliente_form.nombre.data
            direccion = cliente_form.direccion.data
            telefono = cliente_form.telefono.data

            session['cliente_data'] = {
                'nombre': nombre,
                'direccion': direccion,
                'telefono': telefono
            }
        elif 'cliente_data' in session:
            nombre = session['cliente_data'].get('nombre')
            direccion = session['cliente_data'].get('direccion')
            telefono = session['cliente_data'].get('telefono')
        else:
            flash("Por favor complete los datos del cliente", "danger")
            return redirect(url_for('index'))

        if not nombre or not direccion or not telefono:
            flash("Por favor complete todos los datos del cliente", "danger")
            return redirect(url_for('index'))

        subtotal_total = 0
        for pizza in pizzas:
            precio_inicial = PRECIOS[pizza["tamano"]]
            precio_ingredientes = len(
                pizza["ingredientes"]) * COSTO_INGREDIENTE
            subtotal_pieza = precio_inicial + precio_ingredientes
            subtotal_total += subtotal_pieza * int(pizza["cantidad"])

        nueva_venta = Venta(
            nombre_cliente=nombre,
            direccion_cliente=direccion,
            telefono_cliente=telefono,
            total_venta=subtotal_total
        )

        db.session.add(nueva_venta)
        db.session.flush()

        for pizza in pizzas:
            precio_inicial = PRECIOS[pizza["tamano"]]
            precio_ingredientes = len(
                pizza["ingredientes"]) * COSTO_INGREDIENTE
            subtotal_pieza = precio_inicial + precio_ingredientes
            subtotal_total_pizza = subtotal_pieza * int(pizza["cantidad"])

            detalle = DetallePizza(
                venta_id=nueva_venta.id,
                tamano=pizza["tamano"],
                cantidad=pizza["cantidad"],
                subtotal=subtotal_total_pizza
            )

            db.session.add(detalle)
            db.session.flush()

            for ingrediente in pizza["ingredientes"]:
                ing = IngredientePizza(
                    detalle_pizza_id=detalle.id,
                    nombre_ingrediente=ingrediente
                )
                db.session.add(ing)

        try:
            db.session.commit()
            vaciarCarrito()
            session.pop('cliente_data', None)
            flash("Pedido finalizado correctamente", "success")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al procesar el pedido: {str(e)}", "danger")
            return redirect(url_for('index'))

    return redirect(url_for('index'))


@app.route('/eliminar_pizza/<int:indice>', methods=['POST'])
def eliminar_pizza(indice):
    if eliminarPizzaEspecifica(indice):
        flash("Pizza eliminada del carrito", "success")
    else:
        flash("No se pudo eliminar la pizza", "danger")
    return redirect(url_for('index'))


@app.route('/eliminar_carrito', methods=['POST'])
def eliminar_carrito():
    vaciarCarrito()
    flash("Carrito vaciado correctamente", "info")
    return redirect(url_for('index'))

@app.route("/usuario", methods=['GET', 'POST'])
def usuario():
	login=LoginForm(request.form)
	if request.method=='POST':
		print(login.user.data, login.contrasenia.data)
		user=Usuario(user=login.user.data,
			   contrasenia=login.contrasenia.data)
		db.session.add(user)
		db.session.commit()
		return redirect(url_for('index'))
	return render_template('usuario.html', form=login)

@app.route("/pusuario")
def pusuario():
    if Usuario.query.count() == 0: 
        print(Usuario.query.count())
        user=Usuario(user='admin',
                contrasenia='admin')
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    else:
        return render_template('404.html')

if __name__ == '__main__':
    csrf.init_app(app)
    db.init_app(app)
    with app.app_context():
        db.create_all()
    app.run()
