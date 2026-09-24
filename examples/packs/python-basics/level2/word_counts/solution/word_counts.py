def word_counts(words):
    return {word: words.count(word) for word in sorted(set(words))}
