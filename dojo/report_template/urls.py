from django.urls import re_path

from . import views                                                                                                                                                                                         

urlpatterns = [                                                                                                                                                                                             
    re_path(r'^report_templates$', views.view_report_template, name='view_report_template'),                                                                                                                    
    re_path(r'^report_templates/add$', views.add_report_template, name='add_report_template'),                                                                                                                  
    re_path(r'^report_templates/(?P<template_id>\d+)/edit$', views.edit_report_template, name='edit_report_template'),                                                                                          
    re_path(r'^report_templates/(?P<template_id>\d+)/delete$', views.delete_report_template, name='delete_report_template')                                                                                     
]        
