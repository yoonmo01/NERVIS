export function answerMarkdown(text: string): string {
  // Some answers escape paired bold delimiters; preserve inline/fenced code.
  return text.split(/(```[\s\S]*?```|`[^`\n]*`)/g).map((part, index) => index % 2 ? part
    : part.replace(/\\\*\\\*([^\n]+?)\\\*\\\*/g, '**$1**')
      // CommonMark needs a boundary after punctuation before a Korean particle.
      .replace(/\*\*([^*\n]+[)）\]])\*\*(?=[가-힣])/g, '**$1** ')).join('')
}
