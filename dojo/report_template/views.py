import os
import logging
import datetime
import markdown
import bs4
from io import BytesIO
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from dojo.models import Report_Template
from django.conf import settings
from django.http import HttpResponseRedirect, FileResponse
from dojo.utils import add_breadcrumb, get_file_images
from dojo.forms import ReportTemplateForm
from django.urls import reverse
from dojo.authorization.authorization_decorators import user_is_authorized
from dojo.authorization.roles_permissions import Permissions
from docxtpl import DocxTemplate, InlineImage, RichText
from docx.table import Table
from docx.shared import Mm, Pt
from jinja2 import TemplateError, UndefinedError, TemplateSyntaxError, Environment
from PIL import Image


logger = logging.getLogger(__name__)


@user_is_authorized(Report_Template, Permissions.Report_Template_View, 'rid')
def view_report_template(request):
    templates = Report_Template.objects.order_by('pk')

    add_breadcrumb(title="Report templates", top_level=False, request=request)
    return render(request, 'dojo/view_report_template.html', {
        'templates': templates
    })


@user_is_authorized(Report_Template, Permissions.Report_Template_Add, 'rid')
def add_report_template(request):
    if request.method == 'POST':
        form = ReportTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Report template added successfully.',
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse('view_report_template'))
    else:
        form = ReportTemplateForm()

    add_breadcrumb(title="Add report template", top_level=False, request=request)
    return render(request, 'dojo/add_report_template.html', {
        'form': form
    })


@user_is_authorized(Report_Template, Permissions.Report_Template_Edit, 'rid')
def edit_report_template(request, template_id):
    instance = Report_Template.objects.get(pk=template_id)
    if request.method == 'POST':
        form = ReportTemplateForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Report template edited successfully.',
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse('view_report_template'))
    else:
        form = ReportTemplateForm(instance=instance)

    add_breadcrumb(title="Edit report template", top_level=False, request=request)
    return render(request, 'dojo/edit_report_template.html', {
        'form': form,
        'template': instance
    })


@user_is_authorized(Report_Template, Permissions.Report_Template_Delete, 'rid')
def delete_report_template(request, template_id):
    instance = Report_Template.objects.get(pk=template_id)
    instance.delete()

    messages.add_message(
        request,
        messages.SUCCESS,
        'Report template deleted successfully.',
        extra_tags="alert-success",
    )

    return HttpResponseRedirect(reverse('view_report_template'))


def custom_report_template_render(request, template, context):
    if template.template_format == 'Jinja2-DOCX':
        tpl = DocxTemplate(template.file.path)

        def get_vulnerable_endpoints(finding):
            status_list = finding.endpoint_status.all().filter(mitigated=False)
            return [status.endpoint for status in status_list]

        def get_finding_images(finding):
            return [InlineImage(tpl, img.file.path, width=Mm(160)) for img in get_file_images(finding, True)]

        def is_richtext(obj):
            return isinstance(obj, RichText)

        def parseHtmlToDoc(con, bold=False, italic=False, strike=False, color=None, size=None, url_id=None):
            if con.name in ('h1',):
                bold = True
                size = 40
            if con.name in ('h2',):
                bold = True
                size = 36
            if con.name in ('h3',):
                bold = True
                size = 32
            if con.name in ('h4',):
                bold = True
                size = 28
            if con.name in ('h5', 'h6'):
                bold = True
                size = 24
            if con.name in ('strong', 'b'):
                bold = True
            if con.name in ('em', 'i'):
                italic = True
            if con.name in ('s', 'del'):
                strike = True
            if con.name == 'a':
                url_id = tpl.build_url_id(con.get('href'))
                underline = True
                color = '#0044aa'
            res = []
            if con.name == 'img':
                src = con['src']
                img_path = os.path.join(settings.MEDIA_ROOT, 'uploaded_files', src.rsplit('/', 1)[-1])
                img = None
                with Image.open(img_path) as im:
                    w, h = im.size
                    if w > 440:
                        img = InlineImage(tpl, img_path, width=Mm(160))
                    else:
                        img = InlineImage(tpl, img_path)
                res.append(img)
            elif con.name == 'table':
                ...
                # TODO
            elif con.name == 'ul':
                rt = RichText('', bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id)
                for li in con.find_all('li'):
                    liRt = RichText(f'\n· {li.text.strip()}\n', bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id)
                    rt.add(liRt)
                res.append(rt)
            elif con.name == 'ol':
                rt = RichText('', bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id)
                for idx, li in enumerate(con.find_all('li')):
                    liRt = RichText(f'\n{idx + 1}. {li.text.strip()}\n', bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id)
                    rt.add(liRt)
                res.append(rt)
            elif con.name == 'p' and hasattr(con, 'contents'):
                rt = RichText('', bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id)
                for c in con.contents:
                    for element in parseHtmlToDoc(c, bold, italic, strike, color, size, url_id):
                        if isinstance(element, RichText):
                            rt.add(element)
                        else:
                            res.append(rt)
                            res.append(element)
                            rt = RichText('', bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id)
                res.append(rt)
            elif hasattr(con, 'contents'):
                for c in con.contents:
                    res.extend(parseHtmlToDoc(c, bold, italic, strike, color, size, url_id))
            else:
                res.append(RichText(con, bold=bold, italic=italic, strike=strike, color=color, size=size, url_id=url_id))

            return res


        def parse_markdown(value):
            if value == None:
                return None

            html = markdown.markdown(value, extensions=['markdown.extensions.tables'])
            soup = bs4.BeautifulSoup(html, features='html.parser')
            paragraphs = []

            for element in soup.find_all(recursive=False):
                    paragraphs.extend(parseHtmlToDoc(element))

            return paragraphs

        context['date'] = datetime.datetime.now()

        jinja_env = Environment()
        jinja_env.filters['get_vulnerable_endpoints'] = get_vulnerable_endpoints
        jinja_env.filters['get_finding_images'] = get_finding_images
        jinja_env.filters['parse_markdown'] = parse_markdown
        jinja_env.filters['is_richtext'] = is_richtext

        try:
            tpl.render(context, jinja_env)
        except UndefinedError as e:
            messages.add_message(
                request,
                messages.SUCCESS,
                'Failed to generate report: Template undefined variable: ' + str(e),
                extra_tags="alert-danger",
            )

            return HttpResponseRedirect(request.path_info)
        except TemplateSyntaxError as e:
            messages.add_message(
                request,
                messages.SUCCESS,
                'Failed to generate report: Syntax error: ' + str(e),
                extra_tags="alert-danger",
            )

            return HttpResponseRedirect(request.path_info)
        except TemplateError as e:
            messages.add_message(
                request,
                messages.SUCCESS,
                'Failed to generate report: Template error: ' + str(e),
                extra_tags="alert-danger",
            )

            return HttpResponseRedirect(request.path_info)

        with io.BytesIO() as f:
            tpl.save(f)
            return FileResponse(f, as_attachment=True, filename=f'{context["title"]}.docx')
    else:
        raise Http404()
