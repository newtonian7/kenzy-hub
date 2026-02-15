import os
import time
import requests  # Make sure to run: pip install requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = "petroleum-engineer-secret"

# Connect to Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login_page'))

    try:
        user_id = session['user']['id']
        # Fetch fresh balance
        response = supabase.table('profiles').select(
            'balance').eq('id', user_id).single().execute()
        balance = response.data['balance'] if response.data else 0.00
        return render_template('index.html', balance=balance)
    except Exception as e:
        session.pop('user', None)
        return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        action = request.form.get('action')

        try:
            if action == 'signup':
                res = supabase.auth.sign_up(
                    {"email": email, "password": password})
                if res.user:
                    session['user'] = {
                        'id': res.user.id, 'email': res.user.email}
                    return redirect(url_for('home'))
            else:
                res = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password})
                session['user'] = {'id': res.user.id, 'email': res.user.email}
                return redirect(url_for('home'))
        except Exception as e:
            error = str(e)

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/buy-data', methods=['POST'])
def buy_data():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    user_id = session['user']['id']
    price = float(data.get('price'))
    network = data.get('network')
    phone = data.get('phone')

    # 1. Check Balance
    profile = supabase.table('profiles').select(
        'balance').eq('id', user_id).single().execute()
    current_balance = float(profile.data['balance'])

    if current_balance >= price:
        api_key = os.environ.get("DATAMART_API_KEY")

        # --- SIMULATION MODE ---
        if api_key == "simulation_mode_active" or not api_key:
            print(f"🎮 SIMULATION: Pretending to send {network} to {phone}...")
            time.sleep(1)

            new_balance = current_balance - price
            supabase.table('profiles').update(
                {"balance": new_balance}).eq('id', user_id).execute()

            return jsonify({
                "message": f"✅ SUCCESS (SIMULATION): {network} Bundle sent to {phone}!",
                "new_balance": new_balance
            })

        # --- REAL MODE (Future Use) ---
        else:
            # Placeholder for when you get the real key
            return jsonify({"message": "Real API not configured yet"}), 500

    else:
        return jsonify({"message": "Insufficient Balance! Please Top Up."}), 400

# --- PAYSTACK ROUTES (New) ---


@app.route('/get-paystack-key')
def get_paystack_key():
    return jsonify({"key": os.environ.get("PAYSTACK_PUBLIC_KEY")})


@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    data = request.json
    reference = data.get('reference')
    amount = float(data.get('amount'))
    user_id = session['user']['id']

    # 1. Verify with Paystack
    secret_key = os.environ.get("PAYSTACK_SECRET_KEY")
    headers = {"Authorization": f"Bearer {secret_key}"}

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    response = requests.get(url, headers=headers)
    res_data = response.json()

    if res_data['status'] and res_data['data']['status'] == 'success':
        # 2. Update Supabase Balance
        profile = supabase.table('profiles').select(
            'balance').eq('id', user_id).single().execute()
        current_balance = float(profile.data['balance'])

        new_balance = current_balance + amount
        supabase.table('profiles').update(
            {"balance": new_balance}).eq('id', user_id).execute()

        return jsonify({"status": "success", "new_balance": new_balance})

    return jsonify({"status": "failed"}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
