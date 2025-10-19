# mini-zanzibar

Zanzibar clone implementing a subset of its functionality.


## OWASP API Security Zahtevi

Ovaj projekat pokriva ključne zahteve iz OWASP Top 10 i ASVS za API bezbednost. U nastavku su detalji i primeri iz koda:

### 1. Autentikacija i autorizacija
- JWT login endpoint (`/api/login`): korisnik se prijavljuje sa username i lozinkom, dobija JWT token.
- Primer:
	```json
	POST /api/login
	{
		"username": "alice",
		"password": "password123"
	}
	```
- Role-based access control na ACL endpointu (`/api/acl`): samo admin može menjati owner ACL.
- Primer:
	```python
	if data['relation'] == 'owner' and role != 'admin':
			return jsonify({'error': 'Only admin can modify owner ACL'}), 403
	```


### 2. Rate limiting
- Flask-Limiter ograničava broj zahteva na login (5/min po IP), na POST /api/acl (npr. 10/min po IP), i globalno (100/min).
- Primer za login:
	```python
	@limiter.limit("5 per minute")
	def login():
			...
	```
- Primer za ACL:
	```python
	@limiter.limit("10 per minute")
	def add_acl():
			...
	```

### 3. Validacija podataka
- Regex validacija svih ulaznih podataka na endpointima.
- Primer:
	```python
	object_re = r'^[a-zA-Z0-9:_\-]{3,64}$'
	if not re.match(object_re, data['object']):
			return jsonify({'error': 'Invalid object format'}), 400
	```

### 4. Audit log
- Svaka promena ACL-a se loguje sa korisnikom, ulogom i vremenom.
- Primer:
	```python
	logging.info(f"ACL changed by {username} ({role}): {acl_tuple.to_string()}")
	```

### 5. Hash lozinki
- bcrypt se koristi za sigurno čuvanje i proveru lozinki korisnika.
- Primer:
	```python
	if not bcrypt.checkpw(password.encode(), user['password'].encode()):
			return jsonify({'error': 'Invalid credentials'}), 401
	```

### 6. Ne otkriva detalje o greškama
- Povratne vrednosti su opšte, bez stack trace-a ili internih podataka.
- Primer:
	```python
	return jsonify({'error': 'Internal server error'}), 500
	```

### 7. Kontrola pristupa
- Provera korisničke uloge za owner ACL (samo admin može menjati owner relaciju).

### 8. Sigurnost JWT
- JWT tokeni se koriste za autentikaciju i autorizaciju (preporuka: koristi jaku tajnu u produkciji).

### 9. Brute-force zaštita
- Rate limiting na login endpointu sprečava brute-force napade.

---
Ove mere obezbeđuju osnovnu bezbednost API-ja u skladu sa OWASP preporukama za studentski/proof-of-concept projekat.


Students:
- Vladislav Radovic SV 27/2021
- Isidora Aleksic SV 36/2021
- Bojan Zivanic SV 61/2021
