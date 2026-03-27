"""Mock HTTP responses and HTML fixtures for scraper testing."""

import pytest


@pytest.fixture
def simple_html_content():
    """Basic HTML with title and body text."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simple Test Page</title>
        <meta name="description" content="A simple test page">
    </head>
    <body>
        <h1>Welcome to the Test Page</h1>
        <p>This is a paragraph with some content.</p>
        <p>Another paragraph with more text.</p>
    </body>
    </html>
    """


@pytest.fixture
def complex_html_content():
    """HTML with nav, main content, footer."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Complex Test Page - Real Website</title>
        <meta name="description" content="A complex test page with navigation and footer">
        <meta name="author" content="Test Author">
    </head>
    <body>
        <nav>
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/about">About</a></li>
                <li><a href="/contact">Contact</a></li>
            </ul>
        </nav>
        <main>
            <article>
                <h1>Main Article Title</h1>
                <p>This is the main content of the page. It contains important information.</p>
                <p>The article continues with more details about various topics.</p>
                <section>
                    <h2>Subsection Title</h2>
                    <p>Content in a subsection with deeper information.</p>
                </section>
            </article>
            <aside>
                <h3>Related Links</h3>
                <ul>
                    <li><a href="/link1">Related Link 1</a></li>
                    <li><a href="/link2">Related Link 2</a></li>
                </ul>
            </aside>
        </main>
        <footer>
            <p>&copy; 2024 Test Site. All rights reserved.</p>
            <p>Contact: test@example.com</p>
        </footer>
    </body>
    </html>
    """


@pytest.fixture
def malformed_html_content():
    """Broken HTML tags for error testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Malformed HTML Test</title>
    <body>
        <h1>Unclosed tag test
        <p>Missing closing paragraph
        <div>
            <p>Nested unclosed tags
        <script>
            document.write('<p>Unclosed script content');
        </script>
        <div class="broken">
            <span>Overlapping <p>tags</span></p>
        </div>
        <img src="test.jpg">
        <br>
        <input type="text" name="test">
    </body>
    </html>
    """


@pytest.fixture
def minimal_html_content():
    """Very minimal valid HTML."""
    return "<!DOCTYPE html><html><head><title>Minimal</title></head><body><p>Minimal content</p></body></html>"


@pytest.fixture
def rich_article_html():
    """Article-style HTML with headers, paragraphs."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Understanding AI Applications in 2024 - Tech Blog</title>
        <meta name="description" content="A comprehensive guide to AI applications and their impact on modern business">
        <meta name="author" content="Jane Developer">
        <meta property="og:title" content="Understanding AI Applications in 2024">
        <meta property="og:type" content="article">
    </head>
    <body>
        <header>
            <h1>Tech Insights Blog</h1>
            <nav>
                <a href="/">Home</a>
                <a href="/ai">AI Category</a>
                <a href="/tutorials">Tutorials</a>
            </nav>
        </header>
        
        <main>
            <article>
                <header>
                    <h1>Understanding AI Applications in 2024</h1>
                    <p class="meta">Published on March 15, 2024 by <strong>Jane Developer</strong></p>
                </header>
                
                <p class="lead">
                    Artificial Intelligence continues to transform industries across the globe. 
                    This article explores the latest trends and practical applications.
                </p>
                
                <h2>Introduction to Modern AI</h2>
                <p>
                    The landscape of artificial intelligence has evolved dramatically in recent years. 
                    From simple automation to complex decision-making systems, AI applications are 
                    becoming increasingly sophisticated and accessible to businesses of all sizes.
                </p>
                <p>
                    Machine learning models now power everything from recommendation systems to 
                    autonomous vehicles, demonstrating the versatility of modern AI technologies.
                </p>
                
                <h2>Key Application Areas</h2>
                <p>
                    Several sectors have embraced AI with remarkable success. Healthcare, finance, 
                    and manufacturing have seen particularly significant transformations.
                </p>
                
                <h3>Healthcare Innovations</h3>
                <p>
                    AI-powered diagnostic tools are helping doctors identify diseases earlier and 
                    with greater accuracy. Medical imaging analysis, drug discovery, and 
                    personalized treatment plans are just a few examples of AI in action.
                </p>
                
                <h3>Financial Services</h3>
                <p>
                    Banks and financial institutions use AI for fraud detection, risk assessment, 
                    and algorithmic trading. These applications improve security while reducing costs.
                </p>
                
                <h2>Getting Started with AI Development</h2>
                <p>
                    For developers interested in AI, there are numerous frameworks and tools available. 
                    Popular options include TensorFlow, PyTorch, and scikit-learn, each offering 
                    unique advantages for different use cases.
                </p>
                
                <h3>Recommended Tools</h3>
                <ul>
                    <li>TensorFlow - Production-ready ML platform</li>
                    <li>PyTorch - Research-focused framework</li>
                    <li>Hugging Face - NLP and transformer models</li>
                    <li>LangChain - LLM application development</li>
                </ul>
                
                <h2>Conclusion</h2>
                <p>
                    AI applications will continue to grow and evolve. Staying informed about new 
                    developments and best practices is essential for developers and businesses alike.
                </p>
                
                <footer>
                    <p>Tags: <a href="/tags/ai">AI</a>, <a href="/tags/machine-learning">Machine Learning</a>, <a href="/tags/python">Python</a></p>
                </footer>
            </article>
        </main>
        
        <footer>
            <p>&copy; 2024 Tech Insights Blog. All rights reserved.</p>
        </footer>
    </body>
    </html>
    """
