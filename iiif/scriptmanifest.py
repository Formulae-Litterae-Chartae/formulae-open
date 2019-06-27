import json
from urllib.request import urlopen
import ssl
import argparse
import os
import sys
import requests

def create_mapping(args):
    path=os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(args):
        totalpath=os.path.join(path,args)
        files_entry=os.listdir(totalpath)
    else:
        totalpath=path
        files_entry=[args]
    d={}
    ssl._create_default_https_context = ssl._create_unverified_context
    for file in files_entry:
        try:
            with open(os.path.join(totalpath,file),'r') as f:
                data_text=json.load(f)
        except:
            print("Impossible to open the json files "+file)
            continue
        for manifests in data_text:
            for manifest in data_text[manifests]:
                dict_manifest=create_manifest(manifest)
                if dict_manifest==False:
                    continue
                d[manifest["title"]]={"manifest":os.path.join(path,manifest["title"]+".json")}
                os.makedirs(os.path.join(path,manifests), exist_ok=True)
                with open(os.path.join(path,manifests,manifest["title"]+".json"),'w') as f:
                    json.dump(dict_manifest,f)

        with open(os.path.join(path,"Mapping.json"), "w")as f:
            json.dump(d,f)

def create_manifest(manifest):
    filename=manifest["title"]
    #creation of manifest directly by the script
    if not "manifest_link" in manifest.keys():
        label=manifest["label"]
        #update value @id with the path in server of the manifest.json
        dict_image={"@context":"http://iiif.io/api/image/2/context.json","@id":filename,"@type":"sc:Manifest","label":label,	"sequences": [{"canvases": []}]}
        images=manifest["images"]
        for k,v in images.items():
            try:
                data_image=open_data(v)
            except:
                print("Impossible to access at the IIIF image server for "+filename)
                continue
            dict_service={i:data_image[i] for i in data_image if i!='height' and i!='width' and i!='sizes'}
            image={"@id":data_image["@id"],
                   "label":k,
                   "height":data_image["height"],
                   "width":data_image["width"],
                   "images":[
                       {"resource":{
                        "@id":data_image["@id"]+"/full/full/0/default.jpg",
                        "service":dict_service,
                        "height":data_image["height"],
                        "width":data_image["width"]
                        },
                        "on":data_image["@id"]
                       }
                   ],
                    "related":""}
            dict_image["sequences"][0]["canvases"].append(image)
            return dict_image
    else:
        url=manifest["manifest_link"]
        try:
            data=open_data(url)
        except:
            print("The "+filename+" don't work ")
            return False
        if "images" in manifest.keys():
            images=manifest["images"]
            canvases=[]
            for k,v in images.items():
                for sequence in data["sequences"]:
                    for canvase in sequence["canvases"]:
                        if v==canvase["@id"]:
                            canvase["label"]=k
                            canvases.append(canvase)
            for sequence in data["sequences"]:
                del sequence["canvases"]
                sequence["canvases"]=canvases
            return data
        else:
            return data

def open_data(url):
    r=requests.get(url)
    return r.json()


def cmd():
    create_mapping(sys.argv[1])

if __name__ == '__main__':
    cmd()
