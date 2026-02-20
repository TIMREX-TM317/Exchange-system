from typing import Optional


def get_fee_percent(send_method: str, send_detail: Optional[str], amount: float) -> float:
    """
    Returns fee percentage based on the SEND method and amount.
    Fees are always calculated on what the user SENDS.
    """
    m = send_method.strip()
    d = (send_detail or "").strip()

    if m == "PayPal":
        if d == "PayPal Balance":
            if amount < 10:
                return 10.0
            elif amount < 100:
                return 8.0
            else:
                return 7.0
        if d == "Card":
            return 15.0
        # fallback if no detail
        return 10.0

    if m == "CashApp":
        return 10.0
    if m == "Revolut":
        return 10.0
    if m == "Venmo":
        return 10.0
    if m == "Zelle":
        return 10.0
    if m == "Wise":
        return 10.0
    if m == "Bank Transfer":
        return 10.0
    if m == "Skrill":
        return 10.0

    if m == "Paysafe":
        if amount < 50:
            return 25.0
        elif amount < 100:
            return 20.0
        else:
            return 17.0

    if m == "Amazon":
        return 35.0
    if m == "Apple Pay":
        return 25.0
    if m == "Wunschgutschein":
        return 45.0

    return 5.0


def calculate_fee(
    send_method: str,
    send_detail: Optional[str],
    receive_method: str,
    receive_detail: Optional[str],
    amount: float,
) -> dict:
    """
    Returns full fee breakdown dict:
      percent, fee, receive, send_amount, note
    """
    note = ""

    if send_method == "Crypto" and receive_method == "Crypto":
        percent = 3.0
        note = "Crypto to Crypto exchange"
    elif send_method == "Crypto":
        percent = 0.0
        note = "Crypto to other method (0% fee)"
    else:
        percent = get_fee_percent(send_method, send_detail, amount)

    fee_amount = round(amount * percent / 100, 2)

    # CashApp minimum $3
    if send_method == "CashApp" and fee_amount < 3.0:
        fee_amount = 3.0
        note = "Minimum fee of $3 applied"

    return {
        "percent": percent,
        "fee": fee_amount,
        "receive": round(amount - fee_amount, 2),
        "send_amount": amount,
        "note": note,
    }
