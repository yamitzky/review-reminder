import os
from collections import OrderedDict

import requests


GITLAB_URL = os.environ['GITLAB_URL']
GITLAB_TOKEN = os.environ['GITLAB_TOKEN']
GITLAB_PROJECTS = set(os.environ['GITLAB_PROJECTS'].split(','))
SLACK_URL = os.environ['SLACK_URL']
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL')


MR_TEMPLATE="""
    • {assignee} <{url}|*{title}*> {labels} ({created_at}〜)
"""[1:-1]

def main():
    # TODO: pagination
    projects = requests.get(
        f'{GITLAB_URL}/api/v4/projects',
        params={
            'per_page': 100,
            'simple': True,
            'order_by': 'last_activity_at'
        },
        headers={'PRIVATE-TOKEN': GITLAB_TOKEN}
    ).json()
    projects = [p for p in projects
                if p['path_with_namespace'] in GITLAB_PROJECTS]
    project_map = {p['name_with_namespace']: p['web_url'] for p in projects}

    unresolved = OrderedDict()
    for project in projects:
        mrs = requests.get(
            f'{GITLAB_URL}/api/v4/projects/{project["id"]}/merge_requests',
            params={
                'per_page': 100,
                'state': 'opened',
                'order_by': 'created_at'
            },
            headers={'PRIVATE-TOKEN': GITLAB_TOKEN}
        ).json()

        sublist = []
        for mr in mrs:
            if mr.get("assignee"):
                assignee = '@' + mr['assignee']['username']
            else:
                assignee = 'Unassigned'
            if mr['labels']:
                labels = ' '.join([f'`{label}`' for label in mr['labels']])
            else:
                labels = ''
            sublist.append(MR_TEMPLATE.format(**{
                'assignee': assignee,
                'url': mr['web_url'],
                'title': mr['title'],
                'labels': labels,
                'created_at': f'{mr["created_at"][5:7]}/{mr["created_at"][8:10]}'
            }))

        unresolved[project['name_with_namespace']] = sublist

    messages = []
    for project_name, sublist in unresolved.items():
        if sublist:
            sublist = ''.join([f'{l}\n' for l in sublist])
            project_link = f'{project_map[project_name]}/merge_requests'
            messages.append(f'<{project_link}|*{project_name}*>\n{sublist}')

    if not messages:
        return

    message = 'Unmerged MRs!\n\n' + '\n\n'.join(messages)
    payload = {'text': message, 'link_names': 1}
    if SLACK_CHANNEL:
        payload['channel'] = '#' + SLACK_CHANNEL
    requests.post(SLACK_URL, json=payload)


if __name__ == '__main__':
    main()
