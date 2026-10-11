def slugify_title(text):
    import string
    text = text.lower().replace(" ", "-")
    punctuation = string.punctuation.replace("-", "")
    result = ""
    for char in text:
        if char not in punctuation:
            result += char
    return result


def slugify_label(text):
    import string
    text = text.lower().replace(" ", "-")
    punctuation = string.punctuation.replace("-", "")
    result = ""
    for char in text:
        if char not in punctuation:
            result += char
    return result


def slugify_name(text):
    import string
    text = text.lower().replace(" ", "-")
    punctuation = string.punctuation.replace("-", "")
    result = ""
    for char in text:
        if char not in punctuation:
            result += char
    return result


class NameHelper:
    def title(self, text):
        return slugify_title(text)

    def label(self, text):
        return slugify_label(text)

    def name(self, text):
        return slugify_name(text)
