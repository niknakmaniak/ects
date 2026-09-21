\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{ects}[2026/09/21 ECTS course documents]
\LoadClass[11pt,a4paper]{article}
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[french]{babel}
\RequirePackage{lmodern}
\RequirePackage{geometry}
\RequirePackage{microtype}
\RequirePackage{xcolor}
\RequirePackage{titlesec}
\RequirePackage{hyperref}
\RequirePackage{enumitem}

\geometry{margin=2.2cm}
\definecolor{ectsaccent}{HTML}{2C5282}
\hypersetup{colorlinks=true, linkcolor=ectsaccent, urlcolor=ectsaccent}

\titleformat{\section}{\large\bfseries\color{ectsaccent}}{}{0em}{}
\titleformat{\subsection}{\normalsize\bfseries}{}{0em}{}
\setlist[itemize]{leftmargin=1.5em, itemsep=0.25em}
\setlength{\parskip}{0.6em}
