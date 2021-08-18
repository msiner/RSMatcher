
import os
import os.path
import shutil

import markdown
import PyInstaller.__main__

doc_template = """
<html>
<head>
<style>
body {
    font-family: Helvetica, Arial, Sans-Serif;
    margin: auto;
    width: 40em;
}
</style>
</head>
<body>
%s
</body>
"""

def main(): 
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    os.mkdir('dist')
    os.mkdir('dist/RSMatcher')
   
    with open('RSMatcher.md', 'r') as fin:
        with open('dist/RSMatcher/RSMatcher.html', 'w') as fout:
            body = markdown.markdown(
                text=fin.read(),
                output_format='html5',
            )
            fout.write(doc_template % body)

    with open('CHANGELOG.md', 'r') as fin:
        with open('dist/RSMatcher/CHANGELOG.html', 'w') as fout:
            body = markdown.markdown(
                text=fin.read(),
                output_format='html5',
            )
            fout.write(doc_template % body)
        
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    if os.path.exists('RSMatcher.spec'):
        os.unlink('RSMatcher.spec')

    PyInstaller.__main__.run([
        'RSMatcher.py',
        '--distpath',
        './dist/RSMatcher/',
        '--onefile',
    ])


if __name__ == '__main__':
    main()