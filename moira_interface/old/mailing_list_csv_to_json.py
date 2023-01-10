import json
import csv
import sys
import os.path

def main():
    """
    This function takes in a csv file that is the output of 
    qy -s get_end_members_of_list [list-name] > csvfile.csv 
    and converts the data to a JSON file.
    """

    # make sure filename given 
    try:
        assert len(sys.argv) == 2
    except AssertionError:
        print("Error: CSV Filename Not Given")
        exit(1)

    # get name of csv file
    csv_filename = sys.argv[1]
    
    # check that file exists
    try:
        assert os.path.isfile(csv_filename)
    except AssertionError:
        print("Error: CSV File Does Not Exist")
        exit(1)

    # parse csv file data
    json_data = dict()
    # athena accounts ("USER, [name]"); ("KERBEROS, [name]@ATHENA.MIT.EDU");
    # ("KERBEROS, [name]@MIT.EDU") and ("KERBEROS, [name]/root@ATHENA.MIT.EDU")
    json_data["athena_accounts"] = []
    # string emails ("STRING, [name]@[extension]")
    json_data["external_users"] = []
    
    with open(csv_filename, 'r') as csvfile:
        reader = csv.reader(csvfile, skipinitialspace=True, delimiter=',')
        for user_type, user_string in reader:
            if (user_type=="USER"):
                json_data["athena_accounts"].append(user_string)
            elif (user_type=="KERBEROS"):
                if "/" in user_string:
                    kerb, extension = user_string.split("/")
                    if extension=="root@ATHENA.MIT.EDU":
                        json_data["athena_accounts"].append(kerb)
                else:
                    kerb, extension = user_string.split("@")
                    if extension=="ATHENA.MIT.EDU" or extension=="MIT.EDU":
                        json_data["athena_accounts"].append(kerb)
            elif (user_type=="STRING"):
                if ("@" in user_string) and ("<devnull" not in user_string) and \
                        (" removed " not in user_string) and (" " not in user_string):
                    json_data["external_users"].append(user_string)

    # create name of json file to output data
    json_filename = csv_filename.split(".")[0] + ".json"

    # create json file
    with open(json_filename, "w") as jsonfile:
        json.dump(json_data, jsonfile)

# run code
main()
