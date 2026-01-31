"""Enums para el módulo de usuarios."""
import enum
from typing import Dict


class UserRole(str, enum.Enum):
    """Rol del usuario."""
    sales = "sales"
    admin = "admin"
    client = "client"
    marketing = "marketing"
    accounting = "accounting"


class DocumentType(str, enum.Enum):
    """Tipo de documento de identidad."""
    dni = "dni"
    ce = "ce"           # Cédula de extranjería
    ruc = "ruc"
    passport = "passport"
    other = "other"


class PhoneCode(str, enum.Enum):
    """Código telefónico internacional (E.164) y nombre del país."""
    af = "+93"       # Afganistán
    al = "+355"      # Albania
    dz = "+213"      # Argelia
    ad = "+376"      # Andorra
    ao = "+244"      # Angola
    ag = "+1268"     # Antigua y Barbuda
    ar = "+54"       # Argentina
    am = "+374"      # Armenia
    au = "+61"       # Australia
    at = "+43"       # Austria
    az = "+994"      # Azerbaiyán
    bs = "+1242"     # Bahamas
    bh = "+973"      # Baréin
    bd = "+880"      # Bangladés
    bb = "+1246"     # Barbados
    by = "+375"      # Bielorrusia
    be = "+32"       # Bélgica
    bz = "+501"      # Belice
    bj = "+229"      # Benín
    bt = "+975"      # Bután
    bo = "+591"      # Bolivia
    ba = "+387"      # Bosnia y Herzegovina
    bw = "+267"      # Botsuana
    br = "+55"       # Brasil
    bn = "+673"      # Brunéi
    bg = "+359"      # Bulgaria
    bf = "+226"      # Burkina Faso
    bi = "+257"      # Burundi
    kh = "+855"      # Camboya
    cm = "+237"      # Camerún
    ca = "+1"        # Canadá
    cv = "+238"      # Cabo Verde
    cf = "+236"      # República Centroafricana
    td = "+235"      # Chad
    cl = "+56"       # Chile
    cn = "+86"       # China
    co = "+57"       # Colombia
    km = "+269"      # Comoras
    cg = "+242"      # Congo
    cr = "+506"      # Costa Rica
    hr = "+385"      # Croacia
    cu = "+53"       # Cuba
    cy = "+357"      # Chipre
    cz = "+420"      # República Checa
    dk = "+45"       # Dinamarca
    dj = "+253"      # Yibuti
    dm = "+1767"     # Dominica
    do = "+1809"     # República Dominicana (1809, 1829, 1849)
    ec = "+593"      # Ecuador
    eg = "+20"       # Egipto
    sv = "+503"      # El Salvador
    gq = "+240"      # Guinea Ecuatorial
    er = "+291"      # Eritrea
    ee = "+372"      # Estonia
    sz = "+268"      # Esuatini
    et = "+251"      # Etiopía
    fj = "+679"      # Fiyi
    fi = "+358"      # Finlandia
    fr = "+33"       # Francia
    ga = "+241"      # Gabón
    gm = "+220"      # Gambia
    ge = "+995"      # Georgia
    de = "+49"       # Alemania
    gh = "+233"      # Ghana
    gr = "+30"       # Grecia
    gd = "+1473"     # Granada
    gt = "+502"      # Guatemala
    gn = "+224"      # Guinea
    gw = "+245"      # Guinea-Bisáu
    gy = "+592"      # Guyana
    ht = "+509"      # Haití
    hn = "+504"      # Honduras
    hk = "+852"      # Hong Kong
    hu = "+36"       # Hungría
    is_ = "+354"     # Islandia
    in_ = "+91"      # India
    id_ = "+62"      # Indonesia
    ir = "+98"       # Irán
    iq = "+964"      # Irak
    ie = "+353"      # Irlanda
    il = "+972"      # Israel
    it = "+39"       # Italia
    jm = "+1876"     # Jamaica
    jp = "+81"       # Japón
    jo = "+962"      # Jordania
    kz = "+7"        # Kazajistán
    ke = "+254"      # Kenia
    ki = "+686"      # Kiribati
    kp = "+850"      # Corea del Norte
    kr = "+82"       # Corea del Sur
    kw = "+965"      # Kuwait
    kg = "+996"      # Kirguistán
    la = "+856"      # Laos
    lv = "+371"      # Letonia
    lb = "+961"      # Líbano
    ls = "+266"      # Lesoto
    lr = "+231"      # Liberia
    ly = "+218"      # Libia
    li = "+423"      # Liechtenstein
    lt = "+370"      # Lituania
    lu = "+352"      # Luxemburgo
    mo = "+853"      # Macao
    mg = "+261"      # Madagascar
    mw = "+265"      # Malaui
    my = "+60"       # Malasia
    mv = "+960"      # Maldivas
    ml = "+223"      # Malí
    mt = "+356"      # Malta
    mh = "+692"      # Islas Marshall
    mr = "+222"      # Mauritania
    mu = "+230"      # Mauricio
    mx = "+52"       # México
    fm = "+691"      # Micronesia
    md = "+373"      # Moldavia
    mc = "+377"      # Mónaco
    mn = "+976"      # Mongolia
    me = "+382"      # Montenegro
    ma = "+212"      # Marruecos
    mz = "+258"      # Mozambique
    mm = "+95"       # Myanmar
    na = "+264"      # Namibia
    nr = "+674"      # Nauru
    np = "+977"      # Nepal
    nl = "+31"       # Países Bajos
    nz = "+64"       # Nueva Zelanda
    ni = "+505"      # Nicaragua
    ne = "+227"      # Níger
    ng = "+234"      # Nigeria
    mk = "+389"      # Macedonia del Norte
    no = "+47"       # Noruega
    om = "+968"      # Omán
    pk = "+92"       # Pakistán
    pw = "+680"      # Palaos
    ps = "+970"      # Palestina
    pa = "+507"      # Panamá
    pg = "+675"      # Papúa Nueva Guinea
    py = "+595"      # Paraguay
    pe = "+51"       # Perú
    ph = "+63"       # Filipinas
    pl = "+48"       # Polonia
    pt = "+351"      # Portugal
    qa = "+974"      # Catar
    ro = "+40"       # Rumania
    ru = "+7"        # Rusia
    rw = "+250"      # Ruanda
    kn = "+1869"     # San Cristóbal y Nieves
    lc = "+1758"     # Santa Lucía
    vc = "+1784"     # San Vicente y las Granadinas
    ws = "+685"      # Samoa
    sm = "+378"      # San Marino
    st = "+239"      # Santo Tomé y Príncipe
    sa = "+966"      # Arabia Saudita
    sn = "+221"      # Senegal
    rs = "+381"      # Serbia
    sc = "+248"      # Seychelles
    sl = "+232"      # Sierra Leona
    sg = "+65"       # Singapur
    sk = "+421"      # Eslovaquia
    si = "+386"      # Eslovenia
    sb = "+677"      # Islas Salomón
    so = "+252"      # Somalia
    za = "+27"       # Sudáfrica
    ss = "+211"      # Sudán del Sur
    es = "+34"       # España
    lk = "+94"       # Sri Lanka
    sd = "+249"      # Sudán
    sr = "+597"      # Surinam
    se = "+46"       # Suecia
    ch = "+41"       # Suiza
    sy = "+963"      # Siria
    tw = "+886"      # Taiwán
    tj = "+992"      # Tayikistán
    tz = "+255"      # Tanzania
    th = "+66"       # Tailandia
    tl = "+670"      # Timor Oriental
    tg = "+228"      # Togo
    to = "+676"      # Tonga
    tt = "+1868"     # Trinidad y Tobago
    tn = "+216"      # Túnez
    tr = "+90"       # Turquía
    tm = "+993"      # Turkmenistán
    tv = "+688"      # Tuvalu
    ug = "+256"      # Uganda
    ua = "+380"      # Ucrania
    ae = "+971"      # Emiratos Árabes Unidos
    gb = "+44"       # Reino Unido
    us = "+1"        # Estados Unidos
    uy = "+598"      # Uruguay
    uz = "+998"      # Uzbekistán
    vu = "+678"      # Vanuatu
    va = "+379"      # Ciudad del Vaticano
    ve = "+58"       # Venezuela
    vn = "+84"       # Vietnam
    ye = "+967"      # Yemen
    zm = "+260"      # Zambia
    zw = "+263"      # Zimbabue


# Mapeo código telefónico -> nombre del país (relación code_phone <-> país)
phone_code_country: Dict[str, str] = {
    "+93": "Afganistán", "+355": "Albania", "+213": "Argelia", "+376": "Andorra",
    "+244": "Angola", "+1268": "Antigua y Barbuda", "+54": "Argentina", "+374": "Armenia",
    "+61": "Australia", "+43": "Austria", "+994": "Azerbaiyán", "+1242": "Bahamas",
    "+973": "Baréin", "+880": "Bangladés", "+1246": "Barbados", "+375": "Bielorrusia",
    "+32": "Bélgica", "+501": "Belice", "+229": "Benín", "+975": "Bután", "+591": "Bolivia",
    "+387": "Bosnia y Herzegovina", "+267": "Botsuana", "+55": "Brasil", "+673": "Brunéi",
    "+359": "Bulgaria", "+226": "Burkina Faso", "+257": "Burundi", "+855": "Camboya",
    "+237": "Camerún", "+1": "Estados Unidos / Canadá", "+238": "Cabo Verde", "+236": "República Centroafricana",
    "+235": "Chad", "+56": "Chile", "+86": "China", "+57": "Colombia", "+269": "Comoras",
    "+242": "Congo", "+506": "Costa Rica", "+385": "Croacia", "+53": "Cuba", "+357": "Chipre",
    "+420": "República Checa", "+45": "Dinamarca", "+253": "Yibuti", "+1767": "Dominica",
    "+1809": "República Dominicana", "+593": "Ecuador", "+20": "Egipto", "+503": "El Salvador",
    "+240": "Guinea Ecuatorial", "+291": "Eritrea", "+372": "Estonia", "+268": "Esuatini",
    "+251": "Etiopía", "+679": "Fiyi", "+358": "Finlandia", "+33": "Francia", "+241": "Gabón",
    "+220": "Gambia", "+995": "Georgia", "+49": "Alemania", "+233": "Ghana", "+30": "Grecia",
    "+1473": "Granada", "+502": "Guatemala", "+224": "Guinea", "+245": "Guinea-Bisáu",
    "+592": "Guyana", "+509": "Haití", "+504": "Honduras", "+852": "Hong Kong", "+36": "Hungría",
    "+354": "Islandia", "+91": "India", "+62": "Indonesia", "+98": "Irán", "+964": "Irak",
    "+353": "Irlanda", "+972": "Israel", "+39": "Italia", "+1876": "Jamaica", "+81": "Japón",
    "+962": "Jordania", "+7": "Rusia / Kazajistán", "+254": "Kenia", "+686": "Kiribati",
    "+850": "Corea del Norte", "+82": "Corea del Sur", "+965": "Kuwait", "+996": "Kirguistán",
    "+856": "Laos", "+371": "Letonia", "+961": "Líbano", "+266": "Lesoto", "+231": "Liberia",
    "+218": "Libia", "+423": "Liechtenstein", "+370": "Lituania", "+352": "Luxemburgo",
    "+853": "Macao", "+261": "Madagascar", "+265": "Malaui", "+60": "Malasia", "+960": "Maldivas",
    "+223": "Malí", "+356": "Malta", "+692": "Islas Marshall", "+222": "Mauritania",
    "+230": "Mauricio", "+52": "México", "+691": "Micronesia", "+373": "Moldavia",
    "+377": "Mónaco", "+976": "Mongolia", "+382": "Montenegro", "+212": "Marruecos",
    "+258": "Mozambique", "+95": "Myanmar", "+264": "Namibia", "+674": "Nauru", "+977": "Nepal",
    "+31": "Países Bajos", "+64": "Nueva Zelanda", "+505": "Nicaragua", "+227": "Níger",
    "+234": "Nigeria", "+389": "Macedonia del Norte", "+47": "Noruega", "+968": "Omán",
    "+92": "Pakistán", "+680": "Palaos", "+970": "Palestina", "+507": "Panamá",
    "+675": "Papúa Nueva Guinea", "+595": "Paraguay", "+51": "Perú", "+63": "Filipinas",
    "+48": "Polonia", "+351": "Portugal", "+974": "Catar", "+40": "Rumania", "+250": "Ruanda",
    "+1869": "San Cristóbal y Nieves", "+1758": "Santa Lucía", "+1784": "San Vicente y las Granadinas",
    "+685": "Samoa", "+378": "San Marino", "+239": "Santo Tomé y Príncipe", "+966": "Arabia Saudita",
    "+221": "Senegal", "+381": "Serbia", "+248": "Seychelles", "+232": "Sierra Leona",
    "+65": "Singapur", "+421": "Eslovaquia", "+386": "Eslovenia", "+677": "Islas Salomón",
    "+252": "Somalia", "+27": "Sudáfrica", "+211": "Sudán del Sur", "+34": "España",
    "+94": "Sri Lanka", "+249": "Sudán", "+597": "Surinam", "+46": "Suecia", "+41": "Suiza",
    "+963": "Siria", "+886": "Taiwán", "+992": "Tayikistán", "+255": "Tanzania", "+66": "Tailandia",
    "+670": "Timor Oriental", "+228": "Togo", "+676": "Tonga", "+1868": "Trinidad y Tobago",
    "+216": "Túnez", "+90": "Turquía", "+993": "Turkmenistán", "+688": "Tuvalu",
    "+256": "Uganda", "+380": "Ucrania", "+971": "Emiratos Árabes Unidos", "+44": "Reino Unido",
    "+598": "Uruguay", "+998": "Uzbekistán", "+678": "Vanuatu", "+379": "Ciudad del Vaticano",
    "+58": "Venezuela", "+84": "Vietnam", "+967": "Yemen", "+260": "Zambia", "+263": "Zimbabue",
}
