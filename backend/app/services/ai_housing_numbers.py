"""Russian cardinal forms for typed housing quantities, never a spending approval.

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
