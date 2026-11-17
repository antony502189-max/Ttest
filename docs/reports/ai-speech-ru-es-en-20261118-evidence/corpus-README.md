---
license: cc0-1.0
language:
- ab
- af
- am
- ar
- as
- ast
- az
- ba
- bas
- be
- bg
- bn
- br
- ca
- ckb
- cnh
- cs
- cv
- cy
- da
- de
- dv
- dyu
- el
- en
- eo
- es
- et
- eu
- fa
- fi
- fr
- gl
- gn
- ha
- he
- hi
- hsb
- hu
- ia
- id
- ig
- is
- it
- ja
- ka
- kab
- kk
- kmr
- ko
- ky
- lg
- lo
- lt
- lv
- mdf
- mhr
- mk
- ml
- mn
- mr
- mrj
- mt
- myv
- nl
- oc
- or
- pl
- ps
- pt
- quy
- ro
- ru
- rw
- sah
- sat
- sc
- sk
- skr
- sl
- sq
- sr
- sw
- ta
- th
- ti
- tig
- tk
- tok
- tr
- tt
- tw
- ug
- uk
- ur
- uz
- vi
- vot
- yue
- za
- zgh
- zh
- yo
task_categories:
- automatic-speech-recognition
pretty_name: Common Voice Corpus 17.0
size_categories:
- 100B<n<1T
tags:
- mozilla
- foundation
---
# Dataset Card for Common Voice Corpus 17.0

<!-- Provide a quick summary of the dataset. -->

This dataset is an unofficial version of the Mozilla Common Voice Corpus 17. It was downloaded and converted from the project's website https://commonvoice.mozilla.org/.


## Languages
```
Abkhaz, Albanian, Amharic, Arabic, Armenian, Assamese, Asturian, Azerbaijani, Basaa, Bashkir, Basque, Belarusian, Bengali, Breton, Bulgarian, Cantonese, Catalan, Central Kurdish, Chinese (China), Chinese (Hong Kong), Chinese (Taiwan), Chuvash, Czech, Danish, Dhivehi, Dioula, Dutch, English, Erzya, Esperanto, Estonian, Finnish, French, Frisian, Galician, Georgian, German, Greek, Guarani, Hakha Chin, Hausa, Hill Mari, Hindi, Hungarian, Icelandic, Igbo, Indonesian, Interlingua, Irish, Italian, Japanese, Kabyle, Kazakh, Kinyarwanda, Korean, Kurmanji Kurdish, Kyrgyz, Lao, Latvian, Lithuanian, Luganda, Macedonian, Malayalam, Maltese, Marathi, Meadow Mari, Moksha, Mongolian, Nepali, Norwegian Nynorsk, Occitan, Odia, Pashto, Persian, Polish, Portuguese, Punjabi, Quechua Chanka, Romanian, Romansh Sursilvan, Romansh Vallader, Russian, Sakha, Santali (Ol Chiki), Saraiki, Sardinian, Serbian, Slovak, Slovenian, Sorbian, Upper, Spanish, Swahili, Swedish, Taiwanese (Minnan), Tamazight, Tamil, Tatar, Thai, Tigre, Tigrinya, Toki Pona, Turkish, Turkmen, Twi, Ukrainian, Urdu, Uyghur, Uzbek, Vietnamese, Votic, Welsh, Yoruba
```

## How to use
The datasets library allows you to load and pre-process your dataset in pure Python, at scale. The dataset can be downloaded and prepared in one call to your local drive by using the load_dataset function.

For example, to download the Portuguese config, simply specify the corresponding language config name (i.e., "pt" for Portuguese):
```
from datasets import load_dataset

cv_17 = load_dataset("fsicoli/common_voice_17_0", "pt", split="train")
```
Using the datasets library, you can also stream the dataset on-the-fly by adding a streaming=True argument to the load_dataset function call. Loading a dataset in streaming mode loads individual samples of the dataset at a time, rather than downloading the entire dataset to disk.

```
from datasets import load_dataset

cv_17 = load_dataset("fsicoli/common_voice_17_0", "pt", split="train", streaming=True)

print(next(iter(cv_17)))
```

Bonus: create a PyTorch dataloader directly with your own datasets (local/streamed).

### Local
```
from datasets import load_dataset
from torch.utils.data.sampler import BatchSampler, RandomSampler

cv_17 = load_dataset("fsicoli/common_voice_17_0", "pt", split="train")
batch_sampler = BatchSampler(RandomSampler(cv_17), batch_size=32, drop_last=False)
dataloader = DataLoader(cv_17, batch_sampler=batch_sampler)
```

### Streaming
```
from datasets import load_dataset
from torch.utils.data import DataLoader

cv_17 = load_dataset("fsicoli/common_voice_17_0", "pt", split="train")
dataloader = DataLoader(cv_17, batch_size=32)
```

To find out more about loading and preparing audio datasets, head over to hf.co/blog/audio-datasets.



### Dataset Structure
Data Instances
A typical data point comprises the path to the audio file and its sentence. Additional fields include accent, age, client_id, up_votes, down_votes, gender, locale and segment.

### Licensing Information
Public Domain, CC-0


### Citation Information
```
@inproceedings{commonvoice:2020,
  author = {Ardila, R. and Branson, M. and Davis, K. and Henretty, M. and Kohler, M. and Meyer, J. and Morais, R. and Saunders, L. and Tyers, F. M. and Weber, G.},
  title = {Common Voice: A Massively-Multilingual Speech Corpus},
  booktitle = {Proceedings of the 12th Conference on Language Resources and Evaluation (LREC 2020)},
  pages = {4211--4215},
  year = 2020
}
```
---
