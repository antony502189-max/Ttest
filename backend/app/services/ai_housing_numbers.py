"""Russian/Spanish cardinal forms for typed quantities, never a spending approval.

Exact whole-phrase lookup only: never extract a number from unknown user text.
"""


def _forms():
    result = {}
    cases = (
        ('один два три четыре пять шесть семь восемь девять',
         'десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать',
         'двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто',
         'сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот', 'тысяча'),
        ('одного двух трех четырех пяти шести семи восьми девяти',
         'десяти одиннадцати двенадцати тринадцати четырнадцати пятнадцати шестнадцати семнадцати восемнадцати девятнадцати',
         'двадцати тридцати сорока пятидесяти шестидесяти семидесяти восьмидесяти девяноста',
         'ста двухсот трехсот четырехсот пятисот шестисот семисот восьмисот девятисот', 'тысячи'),
    )
    for ones, teens, tens, hundreds, thousand in cases:
        ones, teens, tens, hundreds = (value.split() for value in (ones, teens, tens, hundreds))
        for amount in range(1, 1001):
            if amount == 1000:
                words = [thousand]
            else:
                whole, remainder = divmod(amount, 100)
                words = [hundreds[whole-1]] if whole else []
                if 10 <= remainder < 20:
                    words.append(teens[remainder-10])
                else:
                    ten, one = divmod(remainder, 10)
                    if ten: words.append(tens[ten-2])
                    if one: words.append(ones[one-1])
            result[' '.join(words)] = amount
    return result


AMOUNTS = _forms()


def _spanish_forms():
    # Exact cardinal grammar, bounded to 9999. Keep articles (un/una) out of
    # global normalization: "piso de un dormitorio" is a housing type.
    small = ["uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
    names = {i: word for i, word in enumerate(small, 1)}
    for ten, word in enumerate(["treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"], 3):
        for one in range(10):
            names[ten*10+one] = word + (" y " + names[one] if one else "")
    for hundred, word in enumerate(["ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"], 1):
        for rest in range(100):
            names[hundred*100+rest] = "cien" if hundred == 1 and rest == 0 else word + (" " + names[rest] if rest else "")
    for thousand in range(1, 10):
        prefix = (names[thousand] + " " if thousand > 1 else "") + "mil"
        for rest in range(1000):
            names[thousand*1000+rest] = prefix + (" " + names[rest] if rest else "")
    result = {}
    for number, words in names.items():
        result[words] = number
        if words.endswith("veintiuno"):
            result[words[:-9] + "veintiún"] = number
        elif words.endswith(" uno"):
            result[words[:-3] + "un"] = number
    return result


AMOUNTS.update(_spanish_forms())
# Speech decoders may separate the two morphemes of Russian hundreds.
# These exact spellings preserve their numeric meaning; unknown words remain
# unconsumed and still cause clarification of the entire request.
for _joined, _separated in (("двухсот", "двух сот"), ("трехсот", "трех сот"),
                          ("четырехсот", "четырех сот"), ("пятисот", "пяти сот"),
                          ("шестисот", "шести сот"), ("семисот", "семи сот"),
                          ("восьмисот", "восьми сот"), ("девятисот", "девяти сот")):
    for _words, _amount in list(AMOUNTS.items()):
        if _words == _joined or _words.startswith(_joined + " "):
            AMOUNTS[_words.replace(_joined, _separated, 1)] = _amount
