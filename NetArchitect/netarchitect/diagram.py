"""A small SVG topology sketch; exact physical wiring is in cabling.csv."""
from html import escape


def topology_svg(plan):
    width = 1100
    nodes = ["<svg xmlns='http://www.w3.org/2000/svg' width='1100' height='600' viewBox='0 0 1100 600' role='img' aria-labelledby='title desc'>",
             f"<title id='title'>{escape(plan['name'])} topology</title>",
             "<desc id='desc'>Hub and spoke logical topology with per-site distribution and access switches. Dashed paths are secondary links.</desc>",
             "<style>text{font-family:Arial,sans-serif;fill:#183441;font-size:14px}.small{font-size:12px;fill:#516b77}.box{fill:#edf4f7;stroke:#396577;stroke-width:1.5}.edge{fill:#dceee9;stroke:#26715b;stroke-width:1.5}line{stroke:#627f8c;stroke-width:2}.secondary{stroke-dasharray:7 5;stroke:#b08036}</style>",
             "<rect width='1100' height='600' fill='white'/>",
             f"<text x='35' y='35' style='font-size:24px;font-weight:bold'>{escape(plan['name'])}</text>"]
    def text(x,y,value,cls=""):
        nodes.append(f"<text x='{x}' y='{y}' text-anchor='middle' class='{cls}'>{escape(value)}</text>")
    def box(x,y,w,h,label,kind="box"):
        nodes.append(f"<rect x='{x-w/2}' y='{y}' width='{w}' height='{h}' rx='5' class='{kind}'/>")
        text(x,y+h/2+5,label)
    def line(x1,y1,x2,y2,secondary=False):
        nodes.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' class='{'secondary' if secondary else ''}'/>")
    hub = plan["sites"][0]
    hubs = [e for e in plan["edges"] if e["site_index"]==0]
    hx = [550] if len(hubs)==1 else [410,690]
    remotes = plan["sites"][1:]
    xs = [width*(i+0.5)/len(remotes) for i in range(len(remotes))]
    # Draw connections first so they stay behind the boxes.
    for j,x in enumerate(hx):
        line(550,110,x,160,j==1)
        for remote_x in xs:
            line(x,202,remote_x,345,j==1)
    for remote_x in xs:
        line(remote_x,387,remote_x,425)
        line(remote_x,467,remote_x,505)
    box(550,68,230,42,hub["name"]+"-DS")
    text(550,56,f"{hub['access_switch_count']} access switches at hub", "small")
    for x,e in zip(hx,hubs):
        box(x,160,200,42,e["name"],"edge")
    text(900,35,plan["routing"]["protocol"] + (" over GRE + IPsec" if plan["profile"]=="global" else " routed backbone"))
    for x,s in zip(xs,remotes):
        box(x,345,200,42,s["name"]+"-R1","edge")
        box(x,425,200,42,s["name"]+"-DS")
        box(x,505,200,42,str(s["access_switch_count"])+(" access switch" if s["access_switch_count"] == 1 else " access switches"))
        text(x,570,s["summary"],"small")
    caption = "Logical sketch. Local VLANs terminate on each DS; dashed lines are backup hub paths."
    if plan["profile"] == "global":
        caption = "Logical overlay; provider underlay omitted. See cabling.csv for ports. Dashed lines are backup paths."
    elif plan["profile"] == "metro":
        caption = "Each backbone line is a separate EVPL E-Line. Dashed lines are backup hub paths."
    text(550,595,caption,"small")
    return "\n".join(nodes)+"</svg>\n"
