from django.conf import settings
from django.shortcuts import render_to_response
from django.template import RequestContext
from capra.hazard.models import Hazard, Period
from capra.hazard.reports import render_pdf_response
from geonode.maps.context_processors import resource_urls
from httplib2 import Http
import json 

def index(request): 
    hazards = Hazard.objects.all()
    def periods(hazard): 
        return [{'typename': p.typename, 'length': p.length} for p in hazard.period_set.all()]
    config = [{'hazard': x.name, 'periods': periods(x)} for x in hazards]
    config = json.dumps(config)
    return render_to_response("hazard/index.html",
        context_instance=RequestContext(request, {'config': config}, [resource_urls])
    )

def report(request, format): 
    params = extract_params(request)
    result = request_rest_process("hazard", params)
    if format == 'html':
        data_for_report = {}
        
        geometry = params.get("geometry")
        if geometry.get("type") == "Point":
            geom_data = (geometry.get("coordinates")[0], geometry.get("coordinates")[1]) 
        elif geometry.get("type") == "Line":
            geom_data = "[Distance]"
        elif geometry.get("type") == "Polygon":
            geom_data = "[Area]"

        statistics = result['statistics']
        for layer, stats in statistics.items():
            period = Period.objects.get(typename=layer)
            hazard = period.hazard.name
            if data_for_report.get(hazard):            
               data_for_report[hazard].append((period.length,stats))
               data_for_report[hazard].sort() #ensure nice ordering
            else:
                data_for_report[hazard] = [(period.length,stats)]
        return render_to_response("hazard/report.html",
            context_instance=RequestContext(request, {"data": data_for_report, "geom_data": geom_data}, [resource_urls])
        )
    elif format == 'pdf':
        return render_pdf_response(result)
    else:
        raise Exception("Report requested in invalid format. (Expects .html or .pdf)")

def extract_params(request):
    """
    Examine a report request and extract the parameters that should be 
    included in the corresponding WPS request.
    """
    if request.method == "POST":
        try:
            params = json.loads(request.raw_post_data)
            params["radius"] = radius_for(params["scale"])
            del params["scale"]
            return params
        except:
            pass
    elif request.method == 'GET': 
        try:
            params = json.loads(request.GET['q'])
            params["radius"] = radius_for(params["scale"])
            del params["scale"]
            return params
        except:
            pass
    return {}

def radius_for(scale): 
    """
    Given a scale denominator for the viewport, produce the proper buffer radius
    for the report process. 
    """
    return 12

def request_rest_process(process, params): 
    """
    Make a REST request for the WPS process named, with the provided parameters.
    """
    url = "%srest/process/%s" % (settings.GEOSERVER_BASE_URL, process)
    user, pw = settings.GEOSERVER_CREDENTIALS
    http = Http()
    http.add_credentials(user, pw)
    response, content = http.request(url, "POST", json.dumps(params))
    if (response.status is not 200):
        raise Exception("REST process responded with\nStatus: {0}\nResponse:\n{1}".format(response.status, content))
    return json.loads(content)
