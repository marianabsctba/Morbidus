from identity_svc import mfa

# RFC 6238, apêndice B: segredo ASCII "12345678901234567890" (SHA1), 8 dígitos.
# Com 6 dígitos valem os últimos 6 de cada valor de referência.
SEGREDO_RFC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
VETORES = {59: "287082", 1111111109: "081804", 1111111111: "050471", 1234567890: "005924", 2000000000: "279037"}


def test_vetores_da_rfc_6238():
    for instante, esperado in VETORES.items():
        assert mfa._hotp(SEGREDO_RFC, mfa.passo_atual(instante)) == esperado


def test_tolerancia_de_relogio_e_bloqueio_de_reuso():
    agora = 1234567890
    passo = mfa.passo_atual(agora)
    codigo = mfa._hotp(SEGREDO_RFC, passo)
    assert mfa.confere_totp(SEGREDO_RFC, codigo, None, agora) == passo
    assert mfa.confere_totp(SEGREDO_RFC, codigo, None, agora + 30) == passo  # 30 s depois ainda vale
    assert mfa.confere_totp(SEGREDO_RFC, codigo, None, agora + 90) is None
    assert mfa.confere_totp(SEGREDO_RFC, codigo, passo, agora) is None  # já usado
    assert mfa.confere_totp(SEGREDO_RFC, "12345", None, agora) is None
    assert mfa.confere_totp(SEGREDO_RFC, "abcdef", None, agora) is None


def test_cofre_e_codigos_de_recuperacao():
    cofre = mfa.Cofre("pepper")
    segredo = mfa.novo_segredo()
    cifrado = cofre.cifra(segredo)
    assert segredo not in cifrado and cofre.decifra(cifrado) == segredo
    assert mfa.Cofre("outro").decifra(cifrado) is None
    codigos = mfa.codigos_recuperacao()
    assert len(codigos) == 8 == len(set(codigos))
    assert all(len(mfa.normaliza_recuperacao(c)) == 10 for c in codigos)
    assert "secret=" in mfa.uri_otpauth(segredo, "a@b.com") and "issuer=MORBiDus" in mfa.uri_otpauth(segredo, "a@b.com")
